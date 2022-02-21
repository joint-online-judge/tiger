import asyncio
import platform
import threading
from typing import Any, Generator

import pytest
from _pytest.config import Config

from joj.tiger.app import app
from joj.tiger.config import settings

# from joj.tiger.toolchains import get_toolchains_config


def pytest_configure(config: Config) -> None:
    app.conf.update(
        broker_url="memory://localhost",
        result_backend="file:///tmp",
    )
    # toolchains_config = get_toolchains_config()
    # toolchains_config.pull_images()
    argv = [
        "worker",
        f"--concurrency={settings.workers}",
        # "-Q",
        # ",".join(toolchains_config.generate_queues()),
    ]
    if platform.system() == "Windows":
        argv += ["-P", "solo"]
    t = threading.Thread(target=lambda: app.worker_main(argv=argv))
    t.setDaemon(True)
    t.start()


@pytest.fixture(scope="session")
def event_loop(request: Any) -> Generator[asyncio.AbstractEventLoop, Any, Any]:
    loop = asyncio.get_event_loop_policy().get_event_loop()
    yield loop
