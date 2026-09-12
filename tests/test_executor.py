import multiprocessing

import pytest

from backend.services.conversion_executor import execute_conversion


def test_executor_timeout_terminates_child_process() -> None:
    before = {process.pid for process in multiprocessing.active_children()}
    with pytest.raises(TimeoutError):
        execute_conversion("text-to-docx", [b"hello"], "hello.txt", timeout_seconds=0.001)
    assert {process.pid for process in multiprocessing.active_children()} == before
