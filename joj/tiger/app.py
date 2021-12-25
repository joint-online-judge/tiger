import logging
import platform
from typing import Any, Dict

from celery import Celery, Task
from celery.signals import setup_logging
from loguru import logger
from pydantic_universal_settings import init_settings
from pydantic_universal_settings.cli import async_command

from joj.tiger.config import AllSettings
from joj.tiger.task import TigerTask
from joj.tiger.toolchains import get_toolchains_config


class InterceptHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        # Get corresponding Loguru level if it exists
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where originated the logged message
        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back  # type: ignore
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


@setup_logging.connect
def setup_celery_logging(*args: Any, **kwargs: Any) -> None:
    logging.basicConfig(handlers=[InterceptHandler()], level=logging.INFO)


settings = init_settings(AllSettings, overwrite=False)
backend_url = "rpc://"
broker_url = "amqp://{}:{}@{}:{}/{}".format(
    settings.rabbitmq_username,
    settings.rabbitmq_password,
    settings.rabbitmq_host,
    settings.rabbitmq_port,
    settings.rabbitmq_vhost,
)

app = Celery(
    "tasks",
    backend=backend_url,
    broker=broker_url,
)

# initialize toolchains supported
toolchains_config = get_toolchains_config()

app.conf.update(
    {
        # "task_default_queue": "joj.tiger",
        "result_persistent": False,
        "task_acks_late": True,
        # "task_routes": (
        #     [
        #         ("joj.tiger.*", {"queue": "joj.tiger"}),
        #         # ("joj.horse.*", {"queue": "horse"}),
        #     ],
        # ),
    }
)


# logger.info(app.conf)
# asyncio.run(get_access_token())

# app.user_options["preload"].add(Option("-j", dest="jwt"))


# class ConfigBootstep(bootsteps.Step):
#     def __init__(
#         self, worker: Any, parent: Any, jwt: List[Any], **options: Any
#     ) -> None:
#         access_jwt = jwt[0]
#         app.conf["HEADERS"] = {"Authorization": f"Bearer {access_jwt}"}
#
#
# app.steps["worker"].add(ConfigBootstep)
#
#
# async def compile_task_impl(record_dict: Dict[str, Any], base_url: str) -> None:
#     HEADERS = current_app.conf.get("HEADERS")
#     print("compile_task", record_dict, base_url)
#     record_url = base_url + "/http"
#     case_url = base_url + "/cases/http"
#     total_time_ms = 0
#     total_memory_kb = 0
#     total_score = 0
#     judge_at = datetime.utcnow()
#     async with aiohttp.ClientSession() as session:
#         with AutograderSandbox() as sandbox:
#             for i, case in enumerate(record_dict["cases"]):
#                 result = sandbox.run_command(["echo", "1"])
#                 score = 100
#                 time_ms = int(result.time * 1000)
#                 memory_kb = result.memory
#                 total_score += score
#                 total_time_ms += time_ms
#                 total_memory_kb += memory_kb
#                 case_res = {
#                     "index": i,
#                     "result": {
#                         "status": 1,
#                         "score": score,
#                         "time_ms": time_ms,
#                         "memory_kb": memory_kb,
#                         "execute_status": 1,
#                         "stdout": result.stdout.read().decode(),
#                         "stderr": result.stderr.read().decode(),
#                     },
#                 }
#                 print(f"await case {i}")
#                 async with session.post(
#                     case_url, json=case_res, headers=HEADERS
#                 ) as resp:
#                     print(await resp.text())
#         records_res = {
#             "status": 1,
#             "score": total_score,
#             "time_ms": total_time_ms,
#             "memory_kb": total_memory_kb,
#             "judge_at": str(judge_at),
#         }
#         print("await record")
#         async with session.post(record_url, json=records_res, headers=HEADERS) as resp:
#             print(await resp.text())
#
#
@app.task(name="joj.tiger.compile", bind=True)
@async_command
async def compile_task(self: Task, record_dict: Dict[str, Any], base_url: str) -> None:
    task = TigerTask(self, record_dict, base_url)
    try:
        await task.execute()
    except Exception as e:
        await task.clean()
        raise e
    await task.clean()


def main() -> None:
    toolchains_config.pull_images()
    argv = [
        "worker",
        f"--concurrency={settings.workers}",
        "-Q",
        ",".join(toolchains_config.generate_queues()),
    ]
    if platform.system() == "Windows":
        argv += ["-P", "solo"]
    app.worker_main(argv=argv)


if __name__ == "__main__":
    main()
