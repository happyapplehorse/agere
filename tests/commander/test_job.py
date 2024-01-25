import pytest
import threading
from unittest.mock import Mock

from agere.commander import CallbackDict, Callback, Job, CommanderAsync, tasker, PASS_WORD


@pytest.fixture
def job():
    class JobExample(Job):
        @tasker(PASS_WORD)
        async def task(self):
            pass
    return JobExample()


@pytest.fixture
def commander():
    _commander = CommanderAsync()
    yield _commander
    _commander.exit()


def test_add_callback_functions(job: Job):
    # Setup
    function_info: CallbackDict = {"function": Mock()}
    
    # Action
    job.add_callback_functions(functions_info=function_info, which="at_job_start")
    job.add_callback_functions(functions_info=[function_info, function_info], which="at_job_start")

    # Assert
    assert job.callback is not None
    assert job.callback.at_job_start == [function_info, function_info, function_info]
    with pytest.raises(ValueError):
        job.add_callback_functions(functions_info=function_info, which="error_callback_type")


def test_add_callback(job: Job):
    # Setup
    function_info: CallbackDict = {"function": Mock()}
    callback = Callback(at_job_start=[function_info])

    # Action
    job.add_callback(callback)
    job.add_callback([callback, callback])

    # Assert
    assert job.callback is not None
    assert job.callback.at_job_start == [function_info, function_info, function_info]


def test_exception_callback(commander: CommanderAsync):
    # Setup
    class JobTest(Job):
        @tasker(PASS_WORD)
        async def task(self):
            raise ValueError()
    callback_function = Mock()
    callback = Callback(at_exception=[{"function": callback_function}])
    job = JobTest(callback)

    # Action
    threading.Thread(target=commander.run).start()
    while not commander.running_status:
        pass
    commander.put_job_threadsafe(job)
    while not commander.is_empty():
        pass
    commander.exit()

    # Assert
    assert callback_function.called
    assert job.state == "EXCEPTION"


def test_exit_commander(commander: CommanderAsync):
    # Setup
    class ExitJob(Job):
        @tasker(PASS_WORD)
        async def task(self):
            await self.exit_commander(return_result="exit_code")
    exit_job = ExitJob()

    # Action
    threading.Thread(target=commander.run).start()
    while not commander.running_status:
        pass
    commander.put_job_threadsafe(exit_job)
    while commander.running_status:
        pass

    # Assert
    assert commander.running_status is False
    assert exit_job.state == "COMPLETED"
