import asyncio
import json
import os
from datetime import datetime
from typing import Any, Dict

import websockets

os.environ.setdefault("FORKED_BY_MULTIPROCESSING", "1")

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


async def compile_task_impl(record_dict: Dict[str, Any], base_url: str) -> None:
    print("compile_task", record_dict, base_url)
    record_url = base_url + "/ws"
    case_url = base_url + "/cases/ws"
    total_time_ms = 0
    total_memory_kb = 0
    total_score = 0
    judge_at = datetime.utcnow()
    tasks = []
    async with websockets.connect(case_url) as websocket:
        with AutograderSandbox() as sandbox:
            for i, case in enumerate(record_dict["cases"]):
                result = sandbox.run_command(["echo", "1"])
                score = 100
                time_ms = int(result.time * 1000)
                memory_kb = result.memory
                total_score += score
                total_time_ms += time_ms
                total_memory_kb += memory_kb
                case_res = {
                    "done": i + 1 == len(record_dict["cases"]),
                    "index": i,
                    "result": {
                        "status": 1,
                        "score": score,
                        "time_ms": time_ms,
                        "memory_kb": memory_kb,
                        "execute_status": 1,
                        "stdout": result.stdout.read().decode(),
                        "stderr": result.stderr.read().decode(),
                    },
                }
                print(f"create_task case {i}")
                tasks.append(asyncio.create_task(websocket.send(json.dumps(case_res))))
    await asyncio.gather(*tasks)
    async with websockets.connect(record_url) as websocket:
        records_res = {
            "done": True,
            "result": {
                "status": 1,
                "score": total_score,
                "time_ms": total_time_ms,
                "memory_kb": total_memory_kb,
                "judge_at": str(judge_at),
            },
        }
        print(f"await       record")
        await websocket.send(json.dumps(records_res))


@celery_app.task(name="joj.tiger.compile")
def compile_task(record_dict: Dict[str, Any], base_url: str) -> None:
    asyncio.run(compile_task_impl(record_dict, base_url))
