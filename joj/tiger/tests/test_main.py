import json

from joj.tiger.app import add_task, empty_task, submit_task
from joj.tiger.schemas import ExecuteStatus, SubmitStatus


def test_add() -> None:
    assert add_task.apply_async((2, 3)).get() == 5


def test_create_task() -> None:
    assert empty_task.apply_async().get() is None


def test_submit_task() -> None:
    submit_result = json.loads(submit_task.apply_async(({}, "")).get())
    assert submit_result["submit_status"] == SubmitStatus.accepted.value
    assert submit_result["compile_result"]["return_code"] == 0
    assert submit_result["compile_result"]["stdout"] == "hello world\n"
    assert submit_result["execute_results"][0]["status"] == ExecuteStatus.accepted.value
    assert submit_result["execute_results"][0]["completed_command"]["return_code"] == 0
    assert (
        submit_result["execute_results"][0]["completed_command"]["stdout"]
        == "hello world\n"
    )
