import time

from celery import Celery

celery_app = Celery("tasks", backend="rpc://", broker="pyamqp://localhost//")

celery_app.conf.update(
    {
        "result_persistent": False,
        "task_routes": (
            [("joj.tiger.*", {"queue": "tiger"}), ("joj.horse.*", {"queue": "horse"})],
        ),
    }
)


@celery_app.task(name="joj.tiger.compile")
def compile_task(msg: str) -> str:
    print("waiting 5 secs")
    time.sleep(5)
    print(msg)
    return "success"
