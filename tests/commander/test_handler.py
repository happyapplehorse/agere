import pytest
import threading
from unittest.mock import Mock, AsyncMock

from agere.commander import CallbackDict, Callback, CommanderAsync, PASS_WORD, handler
from agere.commander._commander import HandlerCoroutine


@pytest.fixture
def handler_coroutine():
    return HandlerCoroutine()


@pytest.fixture
def commander():
    _commander = CommanderAsync()
    yield _commander
    _commander.exit()


def test_add_callback_functions(handler_coroutine: HandlerCoroutine):
    # Setup
    function_info: CallbackDict = {"function": Mock()}
    
    # Action
    handler_coroutine.add_callback_functions(functions_info=function_info, which="at_handler_start")
    handler_coroutine.add_callback_functions(functions_info=[function_info, function_info], which="at_handler_start")

    # Assert
    assert handler_coroutine._callback is not None
    assert handler_coroutine._callback.at_handler_start == [function_info, function_info, function_info]
    with pytest.raises(ValueError):
        handler_coroutine.add_callback_functions(functions_info=function_info, which="error_callback_type")


def test_add_callback(handler_coroutine: HandlerCoroutine):
    # Setup
    function_info: CallbackDict = {"function": Mock()}
    callback = Callback(at_handler_start=[function_info])

    # Action
    handler_coroutine.add_callback(callback)
    handler_coroutine.add_callback([callback, callback])

    # Assert
    assert handler_coroutine._callback is not None
    assert handler_coroutine._callback.at_handler_start == [function_info, function_info, function_info]


def test_call_handler(handler_coroutine: HandlerCoroutine):
    # Setup
    commander = Mock()
    handler = Mock()
    handler_coroutine._commander = commander
    
    # Action
    handler_coroutine.call_handler(handler)
    
    # Assert
    commander._call_handler.assert_called_with(handler=handler, parent=handler_coroutine, requester=None)


async def test_put_job(handler_coroutine: HandlerCoroutine):
    # Setup
    commander = AsyncMock()
    job = Mock()
    handler_coroutine._commander = commander
    
    # Action
    await handler_coroutine.put_job(job)
    
    # Assert
    commander._put_job.assert_called_with(job=job, parent=handler_coroutine, requester=None)


def test_exception_callback(handler_coroutine: HandlerCoroutine, commander: CommanderAsync):
    # Setup
    @handler(PASS_WORD)
    async def handler_add(self_handler, obj_list: list):
        obj_list[0] += 1
        raise ValueError("An error.")
    manipulate = [0]
    test_handler = handler_add(manipulate)
    callback_function = Mock()
    function_info: CallbackDict = {"function": callback_function}
    test_handler.add_callback_functions("at_exception", function_info)

    # Action
    threading.Thread(target=commander.run).start()
    while not commander.running_status:
        pass
    commander.call_handler_threadsafe(test_handler)
    while not commander.is_empty():
        pass
    commander.exit()

    # Assert
    assert callback_function.called
    assert manipulate[0] == 1
    assert test_handler.state == "EXCEPTION"
