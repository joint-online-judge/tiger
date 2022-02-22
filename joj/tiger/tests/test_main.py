from joj.tiger.app import add_task, empty_task, submit_task
from joj.tiger.schemas import (
    CompletedCommand,
    ExecuteResult,
    ExecuteStatus,
    SubmitResult,
    SubmitStatus,
)


def test_add() -> None:
    assert add_task.apply_async((2, 3)).get() == 5


def test_create_task() -> None:
    assert empty_task.apply_async().get() is None


def test_submit_task() -> None:
    res = submit_task.apply_async(({}, "")).get()
    assert (
        res
        == SubmitResult(
            submit_status=SubmitStatus.accepted,
            compile_result=CompletedCommand(
                return_code=0,
                stdout=b"",
                stderr="",
                timed_out=False,
                stdout_truncated=False,
                stderr_truncated=False,
                time=0,
                memory=0,
            ),
            execute_results=[
                ExecuteResult(
                    status=ExecuteStatus.accepted,
                    completed_command=CompletedCommand(
                        return_code=0,
                        stdout=b"",
                        stderr="",
                        timed_out=False,
                        stdout_truncated=False,
                        stderr_truncated=False,
                        time=0,
                        memory=0,
                    ),
                )
            ],
        ).json()
    )
