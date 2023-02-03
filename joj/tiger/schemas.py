from enum import Enum
from typing import List, Optional

from pydantic import BaseModel


class StrEnumMixin(str, Enum):
    def __str__(self) -> str:
        return self.value


class RecordState(StrEnumMixin, Enum):
    # waiting
    processing = "processing"  # upload the submission to S3
    queueing = "queueing"  # queue in celery
    retrying = "retrying"  # retry in celery
    # working
    fetched = "fetched"  # fetched by a celery worker
    compiling = "compiling"  # only for compiling languages
    running = "running"
    judging = "judging"
    # fetched = 22
    # ignored = 30
    # done
    accepted = "accepted"
    rejected = "rejected"
    failed = "failed"


class RecordCaseResult(StrEnumMixin, Enum):
    accepted = "accepted"
    wrong_answer = "wrong_answer"
    time_limit_exceeded = "time_limit_exceeded"
    memory_limit_exceeded = "memory_limit_exceeded"
    output_limit_exceeded = "output_limit_exceeded"
    runtime_error = "runtime_error"
    compile_error = "compile_error"
    system_error = "system_error"
    canceled = "canceled"
    etc = "etc"


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
    status: RecordCaseResult
    completed_command: CompletedCommand


class SubmitResult(BaseModel):
    submit_status: RecordState
    compile_result: Optional[CompletedCommand]
    execute_results: Optional[List[ExecuteResult]]
