import asyncio
import logging
from inspect import iscoroutinefunction
from typing import Iterable

from agere.commander._commander import Params, RequiredCallbackDict
from agere.commander._null_logger import get_null_logger


class CallbackDict(RequiredCallbackDict, total=False):
    params: Params


class LLMAsyncAdapter:
    """
    This class converts streaming output (iterable object) from llm into an asynchronous iterable object,
    and allows for adding callback functions at the start and end of the reception.

    Attributes:
        received_message (list): The list of received complete chunks.
    """
    def __init__(
        self,
        at_receiving_start: list[CallbackDict] | None = None,
        at_receiving_end: list[CallbackDict] | None = None,
        logger: logging.Logger | None = None,
    ):
        self.received_message = []
        self._at_receiving_start = at_receiving_start
        self._at_receiving_end = at_receiving_end
        self.logger = logger or get_null_logger()

    async def at_receiving_start(self):
        """This method is called at the start of message reception.

        For complex callbacks, implementation can be achieved by overwriting this method
        """
        if self._at_receiving_start is None:
            return
        await self._do_callback(self._at_receiving_start)

    async def at_receiving_end(self):
        """This method is called at the end of message reception.
        
        For complex callbacks, implementation can be achieved by overwriting this method.
        """
        if self._at_receiving_end is None:
            return
        await self._do_callback(self._at_receiving_end)

    async def _do_callback(self, callback_list: list[CallbackDict]):
        for callback in callback_list:
            function = callback["function"]
            params = callback.get("params")
            if params is None:
                if iscoroutinefunction(function):
                    await function()
                else:
                    function()
            else:
                args = params.get("args", ())
                kwargs = params.get("kwargs", {})
                if iscoroutinefunction(function):
                    await function(*args, **kwargs)
                else:
                    function(*args, **kwargs)

    async def llm_to_async_iterable(
        self,
        response: Iterable,
        at_receiving_start: list[CallbackDict] | None = None,
        at_receiving_end: list[CallbackDict] | None = None,
    ):
        """translate the response from llm to async iterable"""
        if at_receiving_start is not None:
            self._at_receiving_start = at_receiving_start
        if at_receiving_end is not None:
            self._at_receiving_end = at_receiving_end
        self.received_message = []
        is_first_time = True
        response_iter = iter(response)
        while True:
            chunk = await asyncio.to_thread(next, response_iter, None)
            if is_first_time is True:
                await self.at_receiving_start()
                is_first_time = False
            if chunk is None:  # End of the source string
                await self.at_receiving_end()
                break
            self.received_message.append(chunk)
            yield chunk
