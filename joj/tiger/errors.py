class TigerError(Exception):
    pass
    # def __init__(self, error_code: ErrorCode, error_msg: str = ""):
    #     self.error_code = error_code
    #     self.error_msg = error_msg


class WorkerRejectError(TigerError):
    pass


class RetryableError(TigerError):
    pass


class FatalError(TigerError):
    pass
