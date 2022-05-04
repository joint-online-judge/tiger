import asyncio
import logging
import platform
from typing import Any, Dict

from celery import Celery, Task
from celery.signals import setup_logging
from loguru import logger
from pydantic_universal_settings import init_settings
from pydantic_universal_settings.cli import async_command
from tenacity import RetryError

from joj.tiger.config import AllSettings
from joj.tiger.task import TigerTask
from joj.tiger.toolchains import get_toolchains_config
from joj.tiger.utils.retry import retry_init


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
app = Celery("tasks", backend=settings.backend_url, broker=settings.broker_url)

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


@app.task(name="joj.tiger.submit", bind=True)
@async_command
async def submit_task(
    self: Task, record_dict: Dict[str, Any], base_url: str
) -> Dict[str, Any]:
    task = TigerTask(self, record_dict, base_url)
    try:
        submit_result = await task.submit()
    except Exception as e:
        await task.clean()
        raise e
    await task.clean()
    return submit_result.json()


@app.task(name="joj.tiger.empty", bind=True)
@async_command
async def empty_task(self: Task) -> None:
    print(f"{self=}")


@app.task(name="joj.tiger.add", bind=True)
def add_task(self: Task, a: int, b: int) -> int:
    print(f"{self=}")
    return a + b


@retry_init("Celery")
async def try_init_celery() -> None:
    logger.info(app.control.inspect().active())


def startup_event() -> None:  # pragma: no cover
    try:
        asyncio.run(try_init_celery())
    except (RetryError) as e:
        logger.error("Initialization failed, exiting.")
        logger.error(e)
        exit(-1)


def main() -> None:
    toolchains_config.pull_images()
    startup_event()
    argv = [
        "worker",
        f"--concurrency={settings.workers}",
        "-E",
        "-Q",
        ",".join(toolchains_config.generate_queues()),
    ]
    if platform.system() == "Windows":
        argv += ["-P", "solo"]
    if settings.worker_name:
        argv += ["-n", settings.worker_name]
    app.worker_main(argv=argv)


if __name__ == "__main__":
    main()
