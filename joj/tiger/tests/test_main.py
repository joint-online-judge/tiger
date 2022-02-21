from joj.tiger.app import add_task, empty_task


def test_add() -> None:
    assert add_task.apply_async((2, 3)).get() == 5


def test_create_task() -> None:
    assert empty_task.apply_async().get() is None
