from celery import Celery
from celery.worker import WorkController

from joj.tiger.app import empty_task


def test_celery_raw_fixtures(celery_app: Celery, celery_worker: WorkController) -> None:
    assert empty_task.apply_async().get(timeout=10) is None
