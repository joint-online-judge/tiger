from enum import IntEnum
from typing import List, Optional

from pydantic import BaseModel


class ExecuteStatus(IntEnum):
    accepted = 1
    wrong_answer = 2
    time_limit_exceeded = 3
    memory_limit_exceeded = 4
    output_limit_exceeded = 5
    runtime_error = 6
    system_error = 7
    canceled = 8
    etc = 9


class SubmitStatus(IntEnum):
    accepted = 1
    wrong_answer = 2
    time_limit_exceeded = 3
    memory_limit_exceeded = 4
    output_limit_exceeded = 5
    runtime_error = 6
    system_error = 7
    canceled = 8
    compile_error = 9
    etc = 10


class CompletedCommand(BaseModel):
    return_code: int
    stdout: bytes
    stderr: bytes
    timed_out: bool
    stdout_truncated: bool
    stderr_truncated: bool
    time: int
    memory: int


class ExecuteResult(BaseModel):
    status: ExecuteStatus
    completed_command: CompletedCommand


class SubmitResult(BaseModel):
    submit_status: SubmitStatus
    compile_result: Optional[CompletedCommand]
    lint_result: Optional[CompletedCommand]
    execute_results: Optional[List[ExecuteResult]]
