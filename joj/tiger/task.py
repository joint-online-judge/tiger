import asyncio
from datetime import datetime
from io import BytesIO
from typing import Any, Awaitable, Dict, List, cast
from uuid import UUID, uuid4

import orjson
from celery import Task
from celery.app.task import Context
from celery.exceptions import Reject
from fs.osfs import OSFS
from joj.elephant.manager import Manager
from joj.elephant.rclone import RClone
from joj.elephant.storage import LakeFSStorage, TempStorage
from joj.horse_client.models import JudgerCredentials
from loguru import logger

from joj.tiger import errors
from joj.tiger.config import settings
from joj.tiger.horse_apis import HorseClient
from joj.tiger.runner import Runner
from joj.tiger.schemas import (
    CompletedCommand,
    ExecuteResult,
    ExecuteStatus,
    SubmitResult,
    SubmitStatus,
)


class TigerTask:
    id: UUID
    task: Task
    task_id: str
    problem_config: Dict[str, Any]
    record: Dict[str, Any]
    record_fs: OSFS
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

    async def update_state(self) -> None:
        self.task.update_state()  # TODO: update state to horse

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
        await self.update_state()

    async def fetch_problem_config(self) -> None:
        storage = LakeFSStorage(
            endpoint_url=f"http://{settings.lakefs_s3_domain}:{settings.lakefs_port}",
            repo_name=self.credentials.problem_config_repo_name,
            branch_name=self.credentials.problem_config_commit_id,
            username=self.credentials.access_key_id,
            password=self.credentials.secret_access_key,
            host_in_config="lakefs",
        )
        file = BytesIO()
        storage.download("config.json", file)
        file.seek(0)
        self.problem_config = orjson.loads(file.read())
        logger.info(
            f"Task joj.tiger.task[{self.id}] problem config fetched: {self.problem_config}"
        )
        # TODO: fetch test cases

    async def fetch_record(self) -> None:
        source = LakeFSStorage(
            endpoint_url=f"http://{settings.lakefs_s3_domain}:{settings.lakefs_port}",
            repo_name=self.credentials.record_repo_name,
            branch_name=self.credentials.record_commit_id,
            username=self.credentials.access_key_id,
            password=self.credentials.secret_access_key,
            host_in_config="lakefs",
        )
        rclone_config = f"""
            [lakefs]
            type = s3
            provider = Other
            env_auth = false
            access_key_id = {self.credentials.access_key_id}
            secret_access_key = {self.credentials.secret_access_key}
            endpoint = http://{settings.lakefs_s3_domain}:{settings.lakefs_port}
        """
        rclone = RClone(rclone_config)
        self.record_fs = TempStorage()
        manager = Manager(rclone, source, self.record_fs)
        manager.sync_without_validation()  # FIXME: ERROR : : error reading source directory: AccessDenied: Access Denied.
        logger.info(
            f"Task joj.tiger.task[{self.id}] record fetched: {self.record_fs.fs.listdir('/')}"
        )

    async def compile(self) -> CompletedCommand:
        with Runner() as runner:
            res = runner.run_command(["echo", "hello world"])
        logger.info(f"Task joj.tiger.task[{self.id}] compile result: {res}")
        # TODO: update state to horse
        return res

    async def lint(self) -> CompletedCommand:
        with Runner() as runner:
            res = runner.run_command(["echo", "hello world"])
        logger.info(f"Task joj.tiger.task[{self.id}] lint result: {res}")
        # TODO: update state to horse
        return res

    async def execute(self) -> List[ExecuteResult]:
        res = []
        with Runner() as runner:
            for i in range(10):
                status = ExecuteStatus.accepted
                command_res = runner.run_command(["echo", "hello world"])
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
            lint_result = await self.lint()
            execute_results = await self.execute()
            self.submit_res = SubmitResult(
                submit_status=SubmitStatus.accepted,
                compile_result=compile_result,
                lint_result=lint_result,
                execute_results=execute_results,
            )
        except errors.WorkerRejectError as e:
            raise Reject(e.error_msg)
        except errors.RetryableError:
            self.task.retry(countdown=5)
        except Exception as e:
            logger.exception(e)
            # fail the task
            self.submit_res = SubmitResult(submit_status=SubmitStatus.system_error)

    async def submit(self) -> SubmitResult:
        await self.run()
        self.tasks.append(
            asyncio.create_task(
                self.horse_client.submit_record(
                    domain_id=self.record["domain_id"],
                    record_id=self.record["id"],
                    submit_res=self.submit_res,
                    judged_at=self.judged_at,
                )
            )
        )
        return self.submit_res
