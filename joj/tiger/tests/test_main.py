from joj.tiger.app import empty_task


def test_create_task() -> None:
    assert empty_task.apply_async().get() is None
