import pytest
import threading
import time

from unittest.mock import Mock, AsyncMock


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


def test_commander_async_run_auto(job_add, commander: CommanderAsync):
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


def test_commander_async_run_and_exit(job_add, commander: CommanderAsync):
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


def test_wait_for_exit(job_add, commander: CommanderAsync):
    # Setup
    manipulate = [0]
    exit_code = 1
    
    class RunThread(threading.Thread):
        def __init__(self, commander: CommanderAsync, job: Job):
            self.commander = commander
            self.job = job
            super().__init__()

        def run(self):
            self.commander.run_auto(self.job)
    
    run_thread_1 = RunThread(commander, job_add(manipulate))
    run_thread_2 = RunThread(commander, job_add(manipulate))

    # Assert
    assert not commander.running_status
    assert manipulate[0] == 0
    
    # Action
    run_thread_1.start()
    run_thread_2.start()
    exit_code = commander.wait_for_exit()

    # Assert
    run_thread_1.join()
    run_thread_2.join()
    assert not commander.running_status
    assert exit_code is None
    assert manipulate[0] == 2


def test_commander_is_empty(commander, job_add):
    # Setup
    manipulate = [0]
    job = job_add(manipulate)

    # Assert
    assert commander.is_empty()

    # Action
    threading.Thread(target=commander.run_auto, args=(job,)).start()
    commander.wait_for_exit()

    # Assert
    assert manipulate[0] == 1
    assert commander.is_empty()


async def test_handle_callback(commander: CommanderAsync):
    # Setup
    mock_callback = Mock()
    mock_task_node = Mock()
    mock_callback._task_node = mock_task_node
    mock_fn_1 = Mock()
    mock_fn_2 = Mock()
    mock_fn_3 = Mock()
    mock_fn_4 = Mock()
    mock_fn_5 = AsyncMock()
    mock_fn_6 = AsyncMock()
    mock_fn_7 = AsyncMock()
    mock_fn_8 = AsyncMock()
    callback_list = [
        {
            "function": mock_fn_1, "params": {"args": (1, 2), "kwargs": {"key": "value"}},
            "inject_task_node": True,
        },
        {"function": mock_fn_2, "params": {"args": (1, 2), "kwargs": {"key": "value"}}},
        {"function": mock_fn_3, "inject_task_node": True},
        {"function": mock_fn_4},
        {"function": mock_fn_5, "params": {"args": (1, 2), "kwargs": {"key": "value"}}, "inject_task_node": True},
        {"function": mock_fn_6, "params": {"args": (1, 2), "kwargs": {"key": "value"}}},
        {"function": mock_fn_7, "inject_task_node": True},
        {"function": mock_fn_8},
    ]
    mock_callback.at_job_start = callback_list
    mock_callback.at_job_end = []
    setattr(mock_callback, "error_callback_type", None)
    delattr(mock_callback, "error_callback_type")

    # Assert
    with pytest.raises(ValueError):
        await commander._handle_callback(callback=mock_callback, which="error_callback_type")  # type: ignore
    
    # Action
    await commander._handle_callback(callback=mock_callback, which="at_job_end")
    
    # Assert
    assert not mock_fn_1.called
    assert not mock_fn_2.called
    assert not mock_fn_3.called
    assert not mock_fn_4.called
    assert not mock_fn_5.called
    assert not mock_fn_6.called
    assert not mock_fn_7.called
    assert not mock_fn_8.called

    # Action
    await commander._handle_callback(callback=mock_callback, which="at_job_start")

    # Assert
    mock_fn_1.assert_called_once_with(1, 2, key="value", task_node=mock_task_node)
    mock_fn_2.assert_called_once_with(1, 2, key="value")
    mock_fn_3.assert_called_once_with(task_node=mock_task_node)
    mock_fn_4.assert_called_once_with()
    mock_fn_5.assert_called_once_with(1, 2, key="value", task_node=mock_task_node)
    mock_fn_6.assert_called_once_with(1, 2, key="value")
    mock_fn_7.assert_called_once_with(task_node=mock_task_node)
    mock_fn_8.assert_called_once_with()


def test_call_handler_threadsafe(commander: CommanderAsync, job_add, handler_add):
    # Setup
    manipulate = [0]
    job = job_add(manipulate)
    handler = handler_add(manipulate)
    
    # Action
    threading.Thread(target=commander.run, args=(job,)).start()
    while not commander.running_status:
        pass
    commander.call_handler_threadsafe(handler)
    while not commander.is_empty():
        pass
    commander.exit()

    # Assert
    assert manipulate[0] == 2
