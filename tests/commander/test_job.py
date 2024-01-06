import pytest
from unittest.mock import Mock

from agere.commander import CallbackDict, Callback, Job, tasker, PASS_WORD


@pytest.fixture
def job():
    class JobExample(Job):
        @tasker(PASS_WORD)
        async def task(self):
            pass
    return JobExample()

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
