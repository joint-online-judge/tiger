import asyncio
import os
from datetime import datetime
from typing import Any, Dict

import aiohttp
from autograder_sandbox import AutograderSandbox
from celery import Celery, bootsteps, current_app
from celery.bin import Option

os.environ.setdefault("FORKED_BY_MULTIPROCESSING", "1")

celery_app = Celery("tasks", backend="rpc://", broker="pyamqp://localhost//")

celery_app.conf.update(
    {
        "result_persistent": False,
        "task_routes": (
            [("joj.tiger.*", {"queue": "tiger"}), ("joj.horse.*", {"queue": "horse"})],
        ),
    }
)
celery_app.user_options["preload"].add(Option("-j", dest="jwt"))


class ConfigBootstep(bootsteps.Step):
    def __init__(self, worker, jwt=None, **options):
        access_jwt = jwt[0]
        celery_app.conf["HEADERS"] = {"Authorization": f"Bearer {access_jwt}"}


celery_app.steps["worker"].add(ConfigBootstep)


async def compile_task_impl(record_dict: Dict[str, Any], base_url: str) -> None:
    HEADERS = current_app.conf.get("HEADERS")
    print("compile_task", record_dict, base_url)
    record_url = base_url + "/http"
    case_url = base_url + "/cases/http"
    total_time_ms = 0
    total_memory_kb = 0
    total_score = 0
    judge_at = datetime.utcnow()
    async with aiohttp.ClientSession() as session:
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
                print(f"await case {i}")
                async with session.post(
                    case_url, json=case_res, headers=HEADERS
                ) as resp:
                    print(await resp.text())
        records_res = {
            "status": 1,
            "score": total_score,
            "time_ms": total_time_ms,
            "memory_kb": total_memory_kb,
            "judge_at": str(judge_at),
        }
        print(f"await record")
        async with session.post(record_url, json=records_res, headers=HEADERS) as resp:
            print(await resp.text())


@celery_app.task(name="joj.tiger.compile")
def compile_task(record_dict: Dict[str, Any], base_url: str) -> None:
    asyncio.run(compile_task_impl(record_dict, base_url))
