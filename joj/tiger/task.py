import asyncio
from datetime import datetime
from functools import lru_cache
from typing import Any, Awaitable, Dict, List, cast
from uuid import UUID, uuid4

import orjson
from celery import Task
from celery.app.task import Context
from loguru import logger

from joj.elephant.manager import Manager
from joj.elephant.rclone import RClone
from joj.elephant.schemas import Case, Config, Language
from joj.elephant.storage import LakeFSStorage, Storage, TempStorage
from joj.horse_client.models import JudgerCredentials, RecordSubmit
from joj.tiger import errors
from joj.tiger.config import settings
from joj.tiger.horse_apis import HorseClient
from joj.tiger.runner import Runner
from joj.tiger.schemas import (
    CompletedCommand,
    ExecuteResult,
    RecordCaseResult,
    RecordState,
    SubmitResult,
)


@lru_cache
def get_rclone() -> RClone:
    rclone_config = f"""
[lakefs]
type = s3
provider = Other
env_auth = false
access_key_id = {settings.lakefs_username}
secret_access_key = {settings.lakefs_password}
endpoint = http://{settings.lakefs_s3_domain}:{settings.lakefs_port}
    """
    return RClone(rclone_config)


class TigerTask:
    id: UUID
    task: Task
    task_id: str
    config: Language
    config_storage: Storage
    record: Dict[str, Any]
    record_storage: Storage
    horse_client: HorseClient
    credentials: JudgerCredentials
    tasks: List[Awaitable[Any]]
    submit_res: SubmitResult
    judged_at: datetime

    def __init__(self, task: Task, record: Dict[str, Any], base_url: str) -> None:
        self.id = uuid4()  # this id should be unique, be used to create docker images
        self.task = task
        self.task_id = cast(str, cast(Context, task.request).id)
        self.record = record
        self.horse_client = HorseClient(base_url)
        self.tasks = []

    async def login(self) -> None:
        await self.horse_client.login()

    async def claim(self) -> None:
        self.credentials = await self.horse_client.claim_record(
            domain_id=self.record["domain_id"],
            record_id=self.record["id"],
            task_id=self.task_id,
        )
        logger.info(
            f"Task joj.tiger.task[{self.id}] claimed credentials: {self.credentials}"
        )

    async def fetch_problem_config(self) -> None:
        def sync_func() -> None:
            source = LakeFSStorage(
                endpoint_url=f"http://{settings.lakefs_s3_domain}:{settings.lakefs_port}",
                repo_name=self.credentials.problem_config_repo_name,
                branch_name=self.credentials.problem_config_commit_id,
                username=settings.lakefs_username,
                password=settings.lakefs_password,
                host_in_config="lakefs",
            )
            rclone = get_rclone()
            self.config_storage = TempStorage()
            manager = Manager(rclone, source, self.config_storage)
            manager.sync_without_validation()
            logger.info(
                f"Task joj.tiger.task[{self.id}] config fetched: "
                f"{self.config_storage.fs.listdir('/')}"
            )
            try:
                config_json_file = self.config_storage.fs.open("config.json")
                original_config = Config(**orjson.loads(config_json_file.read()))
                config = Config.parse_defaults(original_config)
            except Exception:
                config = Config.generate_default_value()
            logger.debug(f"parsed config: {config}")
            for language in config.languages:
                if language.name == self.record["language"]:
                    self.config = language
                    return
            raise errors.WorkerRejectError(
                f"unsupported language: {self.record['language']}"
            )

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, sync_func)
        logger.info(
            f"Task joj.tiger.task[{self.id}] problem config fetched: {self.config}"
        )

    async def fetch_record(self) -> None:
        def sync_func() -> None:
            source = LakeFSStorage(
                endpoint_url=f"http://{settings.lakefs_s3_domain}:{settings.lakefs_port}",
                repo_name=self.credentials.record_repo_name,
                branch_name=self.credentials.record_commit_id,
                username=settings.lakefs_username,
                password=settings.lakefs_password,
                host_in_config="lakefs",
            )
            rclone = get_rclone()
            self.record_storage = TempStorage()
            manager = Manager(rclone, source, self.record_storage)
            manager.sync_without_validation()
            logger.info(
                f"Task joj.tiger.task[{self.id}] record fetched: "
                f"{self.record_storage.fs.listdir('/')}"
            )

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, sync_func)

    async def compile(self) -> CompletedCommand:
        if len(self.config.compile_args) == 0:
            logger.info(f"Task joj.tiger.task[{self.id}] compile stage skipped")
        with Runner() as runner:
            # TODO: add files
            res = await runner.async_run_command(self.config.compile_args)
        # TODO: update state to horse
        logger.info(f"Task joj.tiger.task[{self.id}] compile result: {res}")
        return res

    async def execute(self) -> List[ExecuteResult]:
        res = []
        with Runner() as runner:
            # TODO: add files, check status & output
            case: Case
            for i, case in enumerate(self.config.cases or []):
                status = RecordCaseResult.accepted
                command_res = await runner.async_run_command(case.execute_args)
                exec_res = ExecuteResult(status=status, completed_command=command_res)
                res.append(exec_res)
                self.tasks.append(
                    asyncio.create_task(
                        self.horse_client.submit_case(
                            domain_id=self.record["domain_id"],
                            record_id=self.record["id"],
                            case_number=i,
                            exec_res=exec_res,
                        )
                    )
                )
        logger.info(f"Task joj.tiger.task[{self.id}] execute result: {res}")
        return res

    async def clean(self) -> None:
        await asyncio.gather(*self.tasks)

    async def run(self) -> None:
        try:
            await self.login()
            await self.claim()
            await asyncio.gather(self.fetch_problem_config(), self.fetch_record())
            self.judged_at = datetime.now()
            compile_result = await self.compile()
            execute_results = await self.execute()
            self.submit_res = SubmitResult(
                submit_status=RecordState.accepted,
                compile_result=compile_result,
                execute_results=execute_results,
            )
        except errors.WorkerRejectError as e:
            logger.exception(e)
            # fail the task
            self.submit_res = SubmitResult(submit_status=RecordState.rejected)
        except errors.RetryableError:
            self.task.retry(countdown=5)
        except Exception as e:
            logger.exception(e)
            # fail the task
            self.submit_res = SubmitResult(submit_status=RecordState.rejected)

    async def submit(self) -> SubmitResult:
        await self.run()
        record_submit = RecordSubmit(
            state=str(self.submit_res.submit_status),
            score=0,  # TODO: calculate score
            time_ms=sum(
                item.completed_command.time
                for item in self.submit_res.execute_results or []
            ),
            memory_kb=sum(
                item.completed_command.memory
                for item in self.submit_res.execute_results or []
            ),
            judged_at=self.judged_at.isoformat(),
        )
        self.tasks.append(
            asyncio.create_task(
                self.horse_client.submit_record(
                    self.record["domain_id"], self.record["id"], record_submit
                )
            )
        )
        return self.submit_res
