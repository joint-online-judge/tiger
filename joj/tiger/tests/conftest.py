import asyncio
import threading
from typing import Any, Generator

import pytest
from _pytest.config import Config
from celery.bootsteps import StartStopStep
from celery.result import _set_task_join_will_block
from celery.worker.consumer.consumer import Consumer

from joj.tiger.app import app, settings, startup


# source: https://github.com/celery/celery/issues/3497
class DisableTaskJoinBlocks(StartStopStep):
    def start(self, c: Consumer) -> None:
        _set_task_join_will_block(False)


def pytest_configure(config: Config) -> None:
    app.steps["consumer"].add(DisableTaskJoinBlocks)
    argv = asyncio.run(startup(settings, test=True))
    t = threading.Thread(target=lambda: app.worker_main(argv=argv))
    t.setDaemon(True)
    t.start()


@pytest.fixture(scope="session")
def event_loop(request: Any) -> Generator[asyncio.AbstractEventLoop, Any, Any]:
    loop = asyncio.get_event_loop_policy().get_event_loop()
    yield loop
