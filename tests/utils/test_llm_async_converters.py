import pytest
from unittest.mock import Mock

from agere.utils.llm_async_converters import LLMAsyncAdapter, CallbackDict


@pytest.fixture
def llm_async_adapter():
    return LLMAsyncAdapter()

async def test_llm_to_async_iterable(llm_async_adapter: LLMAsyncAdapter):
    # Setup
    response = ["a", "b", "c", "d"]
    
    # Action
    async_iterable = llm_async_adapter.llm_to_async_iterable(response=response)
    messages = [x async for x in async_iterable]
    
    # Assert
    assert messages == ["a", "b", "c", "d"]

async def test_callback(llm_async_adapter: LLMAsyncAdapter):
    # Setup
    at_receiving_start_callback = Mock()
    at_receiving_start_callback_dict: CallbackDict = {
        "function": at_receiving_start_callback,
        "params": {"args": ("arg1", "arg2"), "kwargs": {"kwarg": "kwarg"}},
    }
    at_receiving_end_callback = Mock()
    at_receiving_end_callback_dict: CallbackDict = {
        "function": at_receiving_end_callback,
        "params": {"args": ("arg1", "arg2"), "kwargs": {"kwarg": "kwarg"}},
    }
    llm_async_adapter._at_receiving_start = [at_receiving_start_callback_dict]
    llm_async_adapter._at_receiving_end = [at_receiving_end_callback_dict]
    response = ["a", "b", "c", "d"]

    # Action & Assert
    async_iterable = llm_async_adapter.llm_to_async_iterable(response=response)
    async for _ in async_iterable:
        assert at_receiving_start_callback.called
        at_receiving_start_callback.assert_called_with("arg1", "arg2", kwarg="kwarg")
        assert not at_receiving_end_callback.called

    assert at_receiving_end_callback.called
    at_receiving_end_callback.assert_called_with("arg1", "arg2", kwarg="kwarg")
    assert at_receiving_start_callback.call_count == 1
    assert at_receiving_end_callback.call_count == 1
