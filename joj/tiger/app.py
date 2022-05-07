import asyncio
import logging
import platform
import sys
from typing import Any, Dict, List, Union

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
        level: Union[int, str]
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
    logging.basicConfig(
        handlers=[InterceptHandler()],
        level=logging.INFO,
        # FIXME: debug log from celery may destory some our logs
        # level=logging.DEBUG if settings.debug else logging.INFO,
    )


settings = init_settings(AllSettings, overwrite=False)
app = Celery(
    "tasks",
    backend=settings.backend_url,
    broker=settings.broker_url,
    include=["joj.tiger.task"],
)

logger.remove()
logger.add(
    sys.stderr,
    level="DEBUG",
    format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <yellow>"
    + settings.worker_name
    + "</yellow> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
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


@app.task(name="joj.tiger.task", bind=True)
@async_command
async def submit_task(
    self: Task, record_dict: Dict[str, Any], base_url: str
) -> Dict[str, Any]:
    task = TigerTask(self, record_dict, base_url)
    try:
        submit_result = await task.submit()
        logger.info(f"task[{task.id}] submit result: {submit_result}")
    except Exception as e:
        logger.exception("joj.tiger.task task.submit() error")
        raise e
    finally:
        await task.clean()
    return submit_result.json()


def startup_event() -> None:  # pragma: no cover
    @retry_init("Celery")
    async def try_init_celery() -> None:
        logger.info(f"Celery app inspect result: {app.control.inspect().active()}")

    try:
        asyncio.run(try_init_celery())
    except RetryError as e:
        logger.error("Initialization failed, exiting.")
        logger.error(e)
        exit(-1)


def generate_celery_argv(settings: AllSettings, *, test: bool = False) -> List[str]:
    argv = [
        "worker",
        # "--uid=nobody", #FIXME: ModuleNotFoundError: No module named 'celery.apps.worker'
        "--gid=nogroup",
        f"--concurrency={settings.workers}",
        "-E",
    ]
    if platform.system() == "Windows":
        argv += ["-P", "solo"]
    if not test:
        if settings.worker_name:
            argv += ["-n", settings.worker_name]
        toolchains_config.pull_images()
        argv.extend(["-Q", ",".join(toolchains_config.generate_queues())])
    return argv


def main() -> None:
    argv = generate_celery_argv(settings)
    startup_event()
    app.worker_main(argv=argv)


if __name__ == "__main__":
    main()
