import json
from typing import Any, Dict

from celery import Task
from pydantic_universal_settings.cli import async_command

from joj.tiger.app import add_task, app, empty_task
from joj.tiger.schemas import ExecuteStatus, SubmitResult, SubmitStatus
from joj.tiger.task import TigerTask


def test_add() -> None:
    assert add_task.apply_async((2, 3)).get() == 5


def test_create_task() -> None:
    assert empty_task.apply_async().get() is None


@app.task(name="joj.tiger.test_submit", bind=True)
@async_command
async def submit_task_no_horse(self: Task) -> Dict[str, Any]:
    task = TigerTask(self, {}, "")
    compile_result = await task.compile()
    execute_results = await task.execute()
    submit_result = SubmitResult(
        submit_status=SubmitStatus.accepted,
        compile_result=compile_result,
        execute_results=execute_results,
    )
    return submit_result.json()


def test_submit_task() -> None:
    submit_result = json.loads(submit_task_no_horse.apply_async().get())
    assert submit_result["submit_status"] == SubmitStatus.accepted.value
    assert submit_result["compile_result"]["return_code"] == 0
    assert submit_result["compile_result"]["stdout"] == "hello world\n"
    assert submit_result["execute_results"][0]["status"] == ExecuteStatus.accepted.value
    assert submit_result["execute_results"][0]["completed_command"]["return_code"] == 0
    assert (
        submit_result["execute_results"][0]["completed_command"]["stdout"]
        == "hello world\n"
    )
