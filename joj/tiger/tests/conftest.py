from typing import Dict

import pytest


@pytest.fixture(scope="session")
def celery_config() -> Dict[str, str]:
    return {"broker_url": "memory://", "result_backend": "file:///tmp"}
