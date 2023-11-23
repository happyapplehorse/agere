import asyncio
import json
from typing import Iterable, AsyncIterable

from agere.commander import PASS_WORD, CommanderAsync, Callback, BasicJob, Job, tasker, handler
from agere.utils.dispatcher import async_dispatcher_tools_call_for_openai
from agere.utils.llm_async_converters import LLMAsyncAdapter, CallbackDict
from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam

# This srcipt assumes you have the OPENAI_API_KEY environment variable set to a valid OpenAI APK key.


# Example dummy function hard coded to return the same weather
def get_current_weather(location, unit="fahrenheit"):
    """Get the current weather in a given location"""
    if "beijing" in location.lower():
        return json.dumps({"location": "Beijing", "temperature": "10", "unit": "celsius"})
    elif "san francisco" in location.lower():
        return json.dumps({"location": "San Francisco", "temperature": "72", "unit": "fahrenheit"})
    elif "paris" in location.lower():
        return json.dumps({"location": "Paris", "temperature": "22", "unit": "celsius"})
    else:
        return json.dumps({"location": location, "temperature": "unknown"})

tools = [
    {
        "type": "function",
        "function": {
            "name": "get_current_weather",
            "description": "Get the current weather in a given location",
            "parameters": {
                "type": "object",
                "properties": {
                    # You can add a to_user parameter like this to enable the LLM to simultaneously invoke functions and converse with the user.
                    # The dispatcher tool will automatically parse the part addressed to the user from the LLM's response and forward it to the user.
                    "to_user": {
                        "type": "string",
                        "description": (
                            "The content paraphrased for the user." 
                            "The content of this parameter can tell the user what you are about to do, "
                            "or it can be an explanation of the behavior of the function calling. "
                            "For example, 'I'm going to search the internet, please wait a moment.'"
                        ),
                    },
                    "location": {
                        "type": "string",
                        "description": "The city and state, e.g. San Francisco, CA",
                    },
                    "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]},
                },
                "required": ["location"],
            },
        },
    }
]

def openai_chat(context: list[ChatCompletionMessageParam], messages: list[ChatCompletionMessageParam], **kwargs):
    openai_client = OpenAI()
    context.extend(messages)
    response = openai_client.chat.completions.create(
        model="gpt-4",
        messages=context,
        stream=True,
        **kwargs,
    )
    return response


class ResponseJob(Job):
    def __init__(
        self,
        response: Iterable,
        context: list[ChatCompletionMessageParam],
        callback: Callback | None = None,
        at_receiving_start: list[dict] | None = None,
        at_receiving_end: list[dict] | None = None,
    ):
        super().__init__(callback=callback)
        self.response = response
        self.context = context
        self.at_receiving_start = at_receiving_start
        self.at_receiving_end = at_receiving_end

    @tasker(PASS_WORD)
    async def task(self):
        handler = ResponseHandler(self.context).handle_response(
            response=self.response,
            at_receiving_start=self.at_receiving_start,
            at_receiving_end=self.at_receiving_end,
        )
        return handler


class ResponseHandler:
    """A handler to handle response from LLM"""
    def __init__(self, context: list[ChatCompletionMessageParam]):
        self.context = context

    @handler(PASS_WORD)
    async def handle_response(
        self,
        self_handler,
        response,
        at_receiving_start: list[CallbackDict] | None = None,
        at_receiving_end: list[CallbackDict] | None = None,
    ):
        """handler that handle response from LLM"""
        make_role_generator = await async_dispatcher_tools_call_for_openai(
            source=LLMAsyncAdapter().llm_to_async_iterable(
                response=response,
                at_receiving_start=at_receiving_start,
                at_receiving_end=at_receiving_end,
            ),
        )
        to_user_gen = make_role_generator("to_user")
        function_call_gen = make_role_generator("function_call")
        response_to_user_job = BasicJob(OpenaiHandler(self.context).user_handler(user_gen=to_user_gen))
        await self_handler.put_job(job=response_to_user_job)
        function_call_job = BasicJob(OpenaiHandler(self.context).function_call_handler(function_call_gen=function_call_gen))
        await self_handler.put_job(job=function_call_job)


class OpenaiHandler:
    """A handler for processing OpenAI responses"""

    def __init__(self, context: list[ChatCompletionMessageParam]):
        self.context = context
        self.available_functions = {"get_current_weather": get_current_weather}
        self.tools = tools

    @handler(PASS_WORD)
    async def user_handler(self, self_handler, user_gen: AsyncIterable) -> None:
        """Handling the part of the message sent to the user by LLM

        Args:
            user_gen (AsyncIterable): A iterable object including the message to user.
        """
        message_list = []
        
        # Collect and print message.
        print("\033[31mGPT:\033[0m")
        async for char in user_gen:
            print(char, end='', flush=True)
            message_list.append(char)
        print("\n")
            
        # Save response to context.
        collected_message = ''.join(message_list)
        if collected_message:
            self.context.append({"role": "assistant", "content": collected_message})
    
    @handler(PASS_WORD)
    async def function_call_handler(self, self_handler, function_call_gen: AsyncIterable) -> None:
        """Handling the part of the message to call tools

        Args:
            function_call_gen (AsyncIterable): A iterable object including the message to call tools.
        
        """
        function_result_dict = {}
        async for function_call in function_call_gen:
            if not function_call:
                continue
            function_dict = {}
            try:
                function_dict = json.loads(function_call)
            except json.JSONDecodeError as e:
                raise e
            if function_dict.get("name"):
                # call the function
                tool_call_index = function_dict["tool_call_index"]
                tool_call_id = function_dict["tool_call_id"]
                function_name = function_dict["name"]
                function_response = None
                try:
                    function_to_call = self.available_functions[function_name]
                except KeyError:
                    function_to_call = None
                    function_response = f"There is no tool named '{function_name}'."
                function_args = function_dict["arguments"]
                
                function_call_display_str = f"{function_name}({', '.join(f'{k}={v}' for k, v in function_args.items())})"
                
                print(f"Function call: {function_call_display_str}; ID: {tool_call_id}.")
                if function_to_call is not None:
                    function_response = function_to_call(**function_args)
                function_result_dict[tool_call_index] = {
                    "tool_call_id": tool_call_id,
                    "function_name": function_name,
                    "function_args": function_args,
                    "function_result": function_response,
                }
        
        if not function_result_dict:
            return
        # send the function response to GPT
        messages = [
            {
                "tool_call_id": function_result["tool_call_id"],
                "role": "tool",
                "name": function_result["function_name"],
                "content": function_result["function_result"],
            } for function_result in function_result_dict.values()
        ]
        functions = self.tools
        if functions:
            paras = {"messages": messages, "context": self.context, "tools": functions, "tool_choice": "auto"}
        else:
            paras = {"messages": messages, "context": self.context}
        try:
            # add response to context
            self.context.append(
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {"id": one_function_call["tool_call_id"], "function": {"arguments": str(one_function_call["function_args"]), "name": one_function_call["function_name"]}, "type": "function"} for one_function_call in function_result_dict.values()
                    ]
                }
            )
            response = await asyncio.to_thread(openai_chat, **paras)
        except Exception as e:
            raise e

        await self_handler.put_job(ResponseJob(response=response, context=self.context))


if __name__ == "__main__":
    commander = CommanderAsync()
    context = []
    while True:
        user_message = input("\033[32mYOU:\033[0m\n")
        print('')
        if user_message == "exit":
            break
        response = openai_chat(context=context, messages=[{"role": "user", "content": user_message}], tools=tools, tool_choice="auto")
        job = ResponseJob(response=response, context=context)
        commander.run_auto(job=job)
