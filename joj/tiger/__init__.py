from typing import Any, Dict

from autograder_sandbox import AutograderSandbox
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
def compile_task() -> Dict[str, Any]:
    print("compile_task")
    with AutograderSandbox() as sandbox:
        result = sandbox.run_command(["echo", "1"])
    return {
        "time_ms": int(result.time * 1000),
        "memory_kb": result.memory,
        "stdout": result.stdout.read().decode(),
        "stderr": result.stderr.read().decode(),
    }
