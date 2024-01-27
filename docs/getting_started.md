In this tutorial, we will use Agere to build a dialogue agent based on the OpenAI GPT model, which can conduct multiple rounds
of conversation and call tools (for the complete code, please refer to the full example at the end).

Through this tutorial, you will learn the basic process of building an agent with Agere and understand the key parts of Agere.


## Creating The First Job

When building an agent with Agere, we just need to break down the task flow into units, considering what the current task should do.

Firstly, of course, we need to send a message to GPT and get a reply.

So let's define our first Job, like this:

```python hl_lines="1 4 8 10-14"
from agere.commander import PASS_WORD, Job, tasker


class ChatJob(Job):
    def __init__(self, context: list[ChatCompletionMessageParam]):
        # context stores your conversation history and puts the message to be sent at the end
        self.context = context
        super().__init__()

    @tasker(PASS_WORD)
    async def task(self):
        response = openai_chat(context=self.context)
        job = ResponseJob(response=response, context=self.context)
        await self.put_job(job)
```

As you can see, a Job is a class. You can put the resources needed to perform a task in this object. You need to inherit
from the `Job` class to define your own Job, and every Job must define a `task` method, where you can complete the specific
logic of what you want to do.
In a Job, if a task is complex, you can submit the results or remaining parts as a new Job for others to handle after
dealing with your part. To submit a Job, use the `put_job` method.

The `task` method must be decorated with the `tasker` decorator, which requires a password. This password is a reminder
not to place time-consuming, thread-blocking tasks inside the task. You should look at what the password content is to
understand the most important note when using the task, but I can tell you here, it is:
`"I assure all time-consuming tasks are delegated externally."` Of course, you don't need to enter this password
diligently every time. You can import and use it like above, so even if the content of the password changes one day,
you will not be affected.

Here, we define the first Job called `ChatJob`, whose task is to send a message to GPT. After receiving GPT's reply,
the reply content is packaged in a `ResponseJob` and handed over to a new Job for processing.


## Using a Handler

Next, we need to define `ResponseJob`. In the previous step, we only got a reply object, but the real message reception
has not yet started.

Since the process of receiving information in a stream is a time-consuming network process, we need to execute the task of
receiving and processing messages as a handler. In this `ResponseJob`, we create a handler that truly processes messages and
return this handler directly, which will automatically be executed as a handler.

```python hl_lines="13-14"
class ResponseJob(Job):
    def __init__(
        self,
        response: Iterable,
        context: list[ChatCompletionMessageParam],
    ):
        super().__init__()
        self.response = response
        self.context = context

    @tasker(PASS_WORD)
    async def task(self):
        handler = ResponseHandler(self.context).handle_response(response=self.response)
        return handler
```

The task can return a handler, which will be executed.

We previously submitted a `ResponseJob` in the `ChatJob`, and then submitted a handler in the `ResponseJob`. This might seem
a bit cumbersome, but it is done this way to break down the tasks more finely. We will have other situations where `ResponseJob`
will be used later, so it's beneficial to make a finer division here.


## Forked Process
In the previous section, we handed over the reply message object to a handler for processing. Now, we will implement this handler.
A handler is a function while a Job is a class. To define a handler, you only need to decorate a function or method with the
handler decorator. The handler decorator, like tasker, also requires the same password. The handler function must be a coroutine.
The function decorated with the handler decorator will return a `HandlerCoroutine` object, which is a type of `TaskNode` node.
The `HandlerCoroutine` object can be awaited like a normal coroutine object. A handler function can be a regular function or a
method in a class. Unlike normal functions, it will automatically pass a parameter `self_handler`, similar to the `self` parameter
passed in class instance methods. Its name is arbitrary and will be automatically bound to its own `HandlerCoroutine` object.
When calling this function, there is no need to manually pass the `self_handler` parameter. When the handler function is a
regular function, the first parameter is reserved as `self_handler`. When the handler function is a method in a class,
the second parameter, right next to `self`, is reserved as `self_handler`. This allows us to access the `HandlerCoroutine` itself
in the handler function using `self_handler`, just like using `self` to access the class itself.

The messages replied by the GPT model may be regular messages sent to the user or messages for tool invocation. Currently,
GPT can only send one of these two types of messages, but we hope to allow GPT to send both types of messages simultaneously,
that is, to send messages to the user while invoking tools. We can add a `to_user` parameter to the function call parameters
to implement this feature [see the complete example](#complete-example). The `async_dispatcher_tools_call_for_openai` function
provided in Agere's toolset can automatically parse the part sent to the user and the part for tool invocation from the replied
messages in a streaming manner.

In this handler, we use tools provided by Agere to parse the information sent to the user and the tool invocation information,
and send the parsed results to the respective processing functions for handling.

```python hl_lines="1 14 23-24"
from agere.commander import PASS_WORD, handler
from agere.utils.dispatcher import async_dispatcher_tools_call_for_openai
from agere.utils.llm_async_converters import LLMAsyncAdapter


class ResponseHandler:
    """A handler to handle response from LLM"""
    def __init__(self, context: list[ChatCompletionMessageParam]):
        self.context = context

    @handler(PASS_WORD)
    async def handle_response(
        self,
        self_handler,
        response,
    ):
        """handler that handle response from LLM"""
        make_role_generator = await async_dispatcher_tools_call_for_openai(
            source=LLMAsyncAdapter().llm_to_async_iterable(response=response),
        )
        to_user_gen = make_role_generator("to_user")
        function_call_gen = make_role_generator("function_call")
        self_handler.call_handler(OpenaiHandler(self.context).user_handler(user_gen=to_user_gen))
        self_handler.call_handler(OpenaiHandler(self.context).function_call_handler(function_call_gen=function_call_gen))
```

To call a handler, use the `call_handler` method.

Here we also used `LLMAsyncAdapter`, whose function is to convert streaming messages from LLM (synchronous iterable objects)
into asynchronous iterable objects and provide the ability to callback at different stages of message reception.

Here, our process has forked. For messages sent to the user, we hand them over to `user_handler` for processing.
For messages calling tools, we hand them over to `function_call_handler` for processing.


## Circular Process

`user_handler` and `function_call_handler` are both processing GPT's reply messages. We can put them under one class.

```python hl_lines="8-9 29-30 71"
class OpenaiHandler:
    """A handler for processing OpenAI responses"""

    def __init__(self, context: list[ChatCompletionMessageParam]):
        self.context = context
        self.available_functions = {"get_current_weather": get_current_weather}

    @handler(PASS_WORD)
    async def user_handler(self, self_handler, user_gen: AsyncIterable) -> None:
        """Handling the part of the message sent to the user by LLM

        Args:
            user_gen (AsyncIterable): A iterable object including the message to user.
        """
        message_list = []
        
        # Collect and print message.
        print("\n\033[31mGPT:\033[0m")
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
		
		...
		# Complete the function call here and save the results in function_result_dict
        
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
        self.context.extend(messages)
		
        try:
            response = await asyncio.to_thread(openai_chat, context=self.context)
        except Exception as e:
            raise e

        await self_handler.put_job(ResponseJob(response=response, context=self.context))
```

Processing messages sent to the user is relatively simple; they just need to be printed and stored. For tool invocation,
we need to call a function, then return the result of the function to GPT, and submit a `ResponseJob` again to handle the
reply message. This creates a circular task flow.


## Using Callback

So far, our agent is almost completely built. The last issue is how to initiate the next round of dialogue? We can treat the
aforementioned workflow as a complete task, with each execution completing a dialogue, and manually loop this task at the
outermost level. But what if we want to implement such a loop inside the agent? Our idea is to start a new round of dialogue
after one round is completed. The problem is, in processing GPT's reply, two processing lines are branched out: one handles
messages sent to the user, and the other handles tool invocation. Obviously, when one line ends, it cannot ensure that the other
has also ended at that moment. Only when both lines are finished, can a round of dialogue be considered fully complete.

At this point, the status of the `TaskNode` task tree comes into play. When all sub-tasks of a task are completed, the task will
be completed. Therefore, when both lines are complete, their parent node `ChatJob` will be completed. So, we can initiate the
next round of dialogue when `ChatJob` is completed. The method is to add a callback to `ChatJob` that executes upon completion.
In this callback function, we initiate a new round of `ChatJob` tasks, like this:

```python hl_lines="10-16 19-26"
class ChatJob(Job):
    def __init__(self, context: list[ChatCompletionMessageParam]):
        self.context = context
        super().__init__()

    @tasker(PASS_WORD)
    async def task(self):
        response = openai_chat(context=self.context)
        job = ResponseJob(response=response, context=self.context)
        job.add_callback_functions(
            which="at_job_end",
            functions_info={
                "function": self.new_chat_callback,
                "inject_task_node": True
            },
        )
        await self.put_job(job)

    async def new_chat_callback(self, task_node: ChatJob):
        prompt = input("\033[32mYOU:\033[0m\n")
        if prompt == "exit":
            await self.exit_commander(return_result="QUIT")
            return
        self.context.append({"role": "user", "content": prompt})
        new_job = ChatJob(context=self.context)
        await task_node.put_job(job=new_job, parent=task_node.commander)
```
In the callback setup, `which="at_job_end"` specifies that this callback will be executed when this Job is completed.
The setting `"inject_task_node": True` means the `TaskNode` to which this callback function belongs, which in this case is the
`ChatJob` itself, will be automatically passed.

When submitting a new round of `ChatJob`, it should be treated as an entirely new task, not a subtask of the current task.
Therefore, we use `parent=task_node.commander` to specify the parent node of this task. Otherwise, it would become a subtask
of the current task, which is not what we want.


## Last Step

Now, we have completed every step of building this dialogue agent. Let's create a commander and start executing it.

Create a commander like this and hand over the first Job to it:

```python hl_lines="1 5 12-13"
from agere.commander import CommanderAsync


if __name__ == "__main__":
    commander = CommanderAsync()
    context: list[ChatCompletionMessageParam] = []
    prompt = input("\033[32mYOU:\033[0m\n")
    if prompt == "exit":
        print("QUIT")
    else:
        context.append({"role": "user", "content": prompt})
        init_job = ChatJob(context)
        out = commander.run(init_job)
        print(out)
```

When starting a task with `run`, you can also specify `auto_exit=True` to allow the commander to automatically exit after
the task is completed. This `run` statement will be blocked while the commander is running, and will only return after the
commander exits. It can have a `return` value, which can be specified by the `return_result` when the commander exits.


## Complete Example

In this example, we defined two Jobs (`ChatJob` and `ResponseJob`) and three handlers (`response_handler`, `user_handler`,
and `function_call_handler`). We used an `at_job_end` callback in `ChatJob`, and executed these tasks with a commander.

The operational flow of this agent is as shown in the following diagram.
<figure markdown>
  ![flowchart](https://raw.githubusercontent.com/happyapplehorse/happyapplehorse-assets/main/agere/agere_getting_started_flowchart.png)
  <figcaption>The flowchat of the dialogue agent</figcaption>
</figure>

The complete example code is:

``` title="openai_chat_with_tools_within_loop.py"
--8<-- "docs/examples/openai_chat_with_tools_within_loop.py"
```
