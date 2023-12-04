import asyncio
import logging
from typing import AsyncIterator, Callable, AsyncGenerator, Literal

from agere.commander._null_logger import get_null_logger


async def async_dispatcher_tools_call_for_openai(
    source: AsyncIterator,
    logger: logging.Logger | None = None,
    ) -> Callable[[Literal["to_user", "function_call"]], AsyncGenerator]:
    """Dispatch the message to user and tools call.

    It automatically parses the "to_user" parameter in function calls,
    removes it from the function's parameter list, and sends it to the 'to_user' generator.
    The remaining function call parameters are sent to the 'function_call' generator.

    Returns:
        make_generator (Callable[[Literal["to_user", "function_call"]], AsyncGenerator]):
            Factory function, you can pass it the name string of the generator
            to obtain the corresponding generator.

    Example:
        >>> make_generator_for_roles = await async_dispatcher_tools_call_for_openai(an_async_iterator)  
        >>> to_user_generator = make_generator_for_roles("to_user")  
        >>> function_call_generator = make_generator_for_roles("function_call")  
    """
    logger = logger or get_null_logger()
    to_user_queue = asyncio.Queue()
    function_call_queue = asyncio.Queue()

    async def splitter():
        buffer: str = ''
        tool_call_info: str = ''
        before_to_user_content: str = ''
        after_to_user_content: str = ''
        to_user_start_active: bool = False
        to_user_end_active: bool = False
        
        to_user_key_start: int = 0
        to_user_content_start: int = 0
        find_to_user_content_start_position: int = 0
        tool_call_index_now: int = 0
        
        async def put_a_function():
            await function_call_queue.put(
                tool_call_info + before_to_user_content + after_to_user_content + "}"
            )

        async def do_check_to_user_end():
            nonlocal buffer
            nonlocal to_user_content_start
            nonlocal to_user_content_end
            nonlocal to_user_end_active
            if to_user_end_active is True:
                # to_user content finish
                # Put the last to_user content in user queue
                if (last_to_user := buffer[to_user_content_start + 1 : to_user_content_end]):
                    await to_user_queue.put(last_to_user)
                # drop the following ", and possible empty characters
                buffer = buffer[to_user_content_end + 2 :].lstrip()
            else:
                while to_user_content_start < len(buffer) - 1:
                    to_user_content_end = buffer.find('"', to_user_content_start + 1)
                    if to_user_content_end != -1 and buffer[to_user_content_end - 1] != '\\':
                        to_user_end_active = True
                        await do_check_to_user_end()
                        break
                    elif to_user_content_end != -1:
                        # The found double quote does not meet the requirements, continue to search for the next one.
                        # Put the recent to_user content in user queue.
                        await to_user_queue.put(buffer[to_user_content_start + 1 : to_user_content_end + 1])
                        to_user_content_start = to_user_content_end
                    else:
                        # There is no end marker throughout the entire buffer.
                        # Put the recent to_user content in user queue.
                        await to_user_queue.put(buffer[to_user_content_start + 1 :])
                        to_user_content_start = len(buffer) - 1
                        break
        
        async for chunk in source:
            chunk_choice = chunk.choices[0]
            chunk_tool_calls = chunk_choice.delta.tool_calls
            if chunk_choice.finish_reason == "tool_calls":
                if to_user_end_active == to_user_start_active:
                    # Put the last function call.
                    after_to_user_content = buffer
                    await put_a_function()
                await to_user_queue.put(None)
                await function_call_queue.put(None)
                continue
            if chunk_choice.finish_reason is not None:
                await to_user_queue.put(None)
                await function_call_queue.put(None)
                continue

            # Content is not None means no tools call, then put the "content" to user quequ and continue.
            # If no tools call, every chunk will be handle here.
            # Every chunk when no tools call.
            content = chunk_choice.delta.content
            if content is not None:
                await to_user_queue.put(content)
                continue
            
            # This dispatcher only handle tool_calls and content, so other situation will be ignored.
            # Fisrt chunk when call tools.
            if chunk_tool_calls is None:
                # Here includs: 1. the first chunk when call tools; 2. function call; 3. others
                continue

            chunk_tool_call = chunk_tool_calls[0]
            # Get the name of the function called
            # Second chunk when call tools.
            if chunk_tool_call.type == 'function':
                tool_call_index = chunk_tool_call.index
                if tool_call_index_now != tool_call_index:
                    # The second and subsequent function calls.
                    after_to_user_content = buffer
                    if to_user_end_active is True: # The content of 'to_user' exists and is complete.
                        # In cases where there is information for the user, messages from different functions are separated by a newline.
                        await to_user_queue.put("\n")
                    if to_user_end_active == to_user_start_active: # Exclude the case where the parameter parsing is incomplete.
                        await put_a_function()
                    buffer = ''
                    to_user_start_active = False
                    to_user_end_active = False
                function_name = chunk_tool_call.function.name
                tool_call_info = f'{{"tool_call_index": {chunk_tool_call.index}, "tool_call_id": "{chunk_tool_call.id}", "name": "{function_name}", "arguments": '
                tool_call_index_now = tool_call_index
                continue

            # Split the message to user and the function call arguments
            arguments = chunk_tool_call.function.arguments
            buffer += arguments
            
            if to_user_end_active:
                # After to_user content
                continue

            if to_user_start_active is True:
                # In 'to_user' param:
                to_user_content_end = buffer.find('"', to_user_content_start + 1)
                if to_user_content_end != -1 and buffer[to_user_content_end - 1] != '\\':
                    to_user_end_active = True
                await do_check_to_user_end()
                continue

            # Before to_user start flag is found.
            to_user_key_start = buffer.find('"to_user":')
            if to_user_key_start == -1:
                continue # Do not find the "to_user" key, continue to receive the next chunk.
            # In 'to_user' param:
            before_to_user_content = buffer[: to_user_key_start]
            to_user_content_start = buffer.find('"', find_to_user_content_start_position or to_user_key_start + 10)
            if to_user_content_start != -1 and buffer[to_user_content_start - 1] != '\\':
                # In the dictionary, the double quotes representing key-value are regular double quotes '"',
                # while double quotes inside strings are escaped double quotes '\"'.
                # We can determine whether the double quotes are in a string or represent a key-value pari by
                # checking if the character before the double quotes is '\'.
                # In content of to_user.
                to_user_start_active = True
                to_user_content_end = buffer.find('"', to_user_content_start + 1)
                if to_user_content_end != -1 and buffer[to_user_content_end - 1] != '\\':
                    # Content of to_user finish.
                    to_user_end_active = True
                await do_check_to_user_end()
            elif to_user_content_start != -1:
                # Under normal circumstances, the code would not execute to this point.
                # This branch is used to handle the exceptional case
                # where the string content of the 'to_user' is not immediately followed after '"to_user":'
                find_to_user_content_start_position = to_user_content_start

    role_queue_dict = {"to_user":to_user_queue, "function_call":function_call_queue}
    
    def make_generator(role_name: str):
        async def generator():
            while True:
                value = await role_queue_dict[role_name].get()
                if value is None: # End of the queue
                    break
                yield value
        return generator()
    
    splitter_task = asyncio.create_task(splitter())
    
    return make_generator
