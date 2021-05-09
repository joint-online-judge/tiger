from datetime import datetime
from typing import Any, Dict

from autograder_sandbox import AutograderSandbox
from celery import Celery, current_task

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
def compile_task(record_dict: Dict[str, Any]) -> Dict[str, Any]:
    print("compile_task", record_dict)
    total_time_ms = 0
    total_memory_kb = 0
    total_score = 0
    judge_at = datetime.utcnow()
    with AutograderSandbox() as sandbox:
        for i, case in enumerate(record_dict["cases"]):
            result = sandbox.run_command(["echo", "1"])
            score = 100
            time_ms = int(result.time * 1000)
            memory_kb = result.memory
            meta = {
                "index": i,
                "status": 1,
                "score": score,
                "time_ms": time_ms,
                "memory_kb": memory_kb,
                "execute_status": 1,
                "stdout": result.stdout.read().decode(),
                "stderr": result.stderr.read().decode(),
            }
            current_task.update_state(state="PROGRESS", meta=meta)
            total_score += score
            total_time_ms += time_ms
            total_memory_kb += memory_kb
    return {
        "status": 1,
        "score": total_score,
        "time_ms": total_time_ms,
        "memory_kb": total_memory_kb,
        "judge_at": judge_at,
    }
