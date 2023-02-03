import asyncio
import logging
import platform
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
        # FIXME: debug log from celery may destroy some our logs
        # level=logging.DEBUG if settings.debug else logging.INFO,
    )


settings = init_settings(AllSettings, overwrite=False)
if settings.debug:
    logger.debug(f"settings: {settings}")
app = Celery(
    "tasks",
    backend=settings.backend_url,
    broker=settings.broker_url,
    include=["joj.tiger.task"],
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
    submit_result = await task.submit()
    logger.info(f"task[{task.id}] submit result: {submit_result}")
    await task.clean()
    return submit_result.json()


async def startup(settings: AllSettings, *, test: bool = False) -> List[str]:
    async def startup_event() -> None:  # pragma: no cover
        @retry_init("Celery")
        async def try_init_celery() -> None:
            logger.info(f"Celery app inspect result: {app.control.inspect().active()}")

        try:
            await try_init_celery()
        except RetryError as e:
            logger.error("Initialization failed, exiting.")
            logger.error(e)
            exit(-1)

    async def generate_celery_argv(
        settings: AllSettings, *, test: bool = False
    ) -> List[str]:
        argv = [
            "worker",
            # "--uid=nobody", #FIXME: ModuleNotFoundError: No module named 'celery.apps.worker'
            "--gid=nogroup",
            f"--concurrency={settings.workers}",
            "-E",
        ]
        if platform.system() == "Windows":
            argv += ["-P", "solo"]
        if worker_name := settings.horse_username:
            argv += ["-n", worker_name]
        if not test:
            await toolchains_config.pull_images()
            argv.extend(["-Q", ",".join(toolchains_config.generate_queues())])
        return argv

    _, argv = await asyncio.gather(
        startup_event(), generate_celery_argv(settings, test=test)
    )
    logger.debug(f"celery argv: {argv}")
    return argv


async def main() -> None:
    app.worker_main(argv=await startup(settings))


if __name__ == "__main__":
    if platform.system() != "Windows":
        import uvloop

        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    asyncio.run(main())
