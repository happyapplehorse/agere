import pytest
import threading
import time

from agere.commander._commander import (
    PASS_WORD,
    CommanderAsync,
    BasicJob,
    handler,
    Job,
    _is_first_param_bound,
)


@pytest.fixture
def handler_add():
    @handler(PASS_WORD)
    async def _handler_add(self_handler, list_obj) -> None:
        assert len(list_obj) >= 1
        list_obj[0] += 1
    return _handler_add


@pytest.fixture
def job_add(handler_add):
    def _job_add(list_obj: list) -> Job:
        job = BasicJob(job_content=handler_add(list_obj=list_obj))
        return job
    return _job_add


@pytest.fixture
def commander():
    _commander = CommanderAsync()
    yield _commander
    _commander.exit()


async def test_commander_async_initialization():
    # Action
    commander = CommanderAsync()
    
    # Assert
    assert commander is not None
    assert not commander.running_status


async def test_handler_coroutine_await(handler_add):
    # Setup    
    manipulate = [0]
    handler = handler_add(manipulate)
    handler._parent = "Null"

    # Action
    await handler

    # Assert
    assert manipulate[0] == 1


def outer_function():
    def nested_function():
        pass
    return nested_function

class TClass:
    @staticmethod
    def static_method():
        pass

    @classmethod
    def class_method(cls):
        pass
    
    def instance_method(self):
        pass

def test_is_first_param_bound():
    # Setup
    t_class = TClass()

    # Assert
    assert not _is_first_param_bound(outer_function)
    assert not _is_first_param_bound(outer_function())
    assert not _is_first_param_bound(t_class.static_method)
    assert _is_first_param_bound(t_class.class_method)
    assert _is_first_param_bound(t_class.instance_method)
    assert not _is_first_param_bound(TClass.static_method)
    assert _is_first_param_bound(TClass.class_method)
    assert _is_first_param_bound(TClass.instance_method)


def test_commander_async_run_auto(job_add, commander):
    # Setup
    manipulate = [0]
    job = job_add(manipulate)

    # Assert
    assert manipulate[0] == 0

    # Action
    dose_new_loop = commander.run_auto(job)

    # Assert
    assert dose_new_loop is True
    assert manipulate[0] == 1
    assert not commander.running_status


def test_commander_async_run_and_exit(job_add, commander):
    # Setup
    manipulate = [0]
    exit_code = [None]
    
    class RunThread(threading.Thread):
        def __init__(self, commander: CommanderAsync, job: Job, exit_code: list):
            self.commander = commander
            self.job = job
            self.exit_code = exit_code
            super().__init__()

        def run(self):
            self.exit_code[0] = self.commander.run(self.job)
    
    run_thread_1 = RunThread(commander, job_add(manipulate), exit_code)

    # Assert
    assert manipulate[0] == 0
    assert not commander.running_status

    # Action
    run_thread_1.start()
    time.sleep(0.1)

    # Assert
    assert commander.running_status

    # Action
    commander.exit(1)

    # Assert
    assert manipulate[0] == 1
    assert exit_code[0] == 1
    assert not commander.running_status

    # Action
    run_thread_2 = RunThread(commander, job_add(manipulate), exit_code)
    run_thread_2.start()
    time.sleep(0.1)

    # Assert
    assert commander.running_status

    # Action
    commander.exit(2, wait=False)
    run_thread_2.join()

    # Assert
    assert manipulate[0] == 2
    assert exit_code[0] == 2
    assert not commander.running_status
