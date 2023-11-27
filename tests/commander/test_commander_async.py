import asyncio
import pytest

from agere.commander._commander import PASS_WORD, CommanderAsync, BasicJob, HandlerCoroutine, tasker, handler


@pytest.mark.asyncio
async def test_commander_async_initialization():
    commander = CommanderAsync()
    assert commander is not None
    assert not commander.running_status

@handler(PASS_WORD)
async def sample_task_for_await(self_handler):
    return "handler result"

@pytest.mark.asyncio
async def test_handler_coroutine_await():

    handler = sample_task_for_await()
    handler._parent = "Null"

    result = await handler
    assert result == "handler result"

@handler(PASS_WORD)
async def sample_task_for_run_auto(self_handler, manipulate):
    manipulate[0] = 1

def test_commander_async_run_auto():
    commander = CommanderAsync()

    manipulate = [0]

    job = BasicJob(job_content=sample_task_for_run_auto(manipulate=manipulate))
    
    assert manipulate[0] == 0
    dose_new_loop = commander.run_auto(job)
    assert dose_new_loop is True
    assert manipulate[0] == 1
    assert not commander.running_status
