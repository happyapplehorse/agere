A handler is like a function call, but it has the structure of a `TaskNode`, allowing for better management and
tracking of the parent-child relationships and status of tasks. You can think of it as delegating tasks to subordinates.


Similar to a Job, a handler must be decorated with the `handler` decorator and requires a passphrase. Each function
decorated with the `handler` decorator returns a `HandlerCoroutine` object, which is a `TaskNode` node. The `HandlerCoroutine`
object can be awaited like a normal coroutine object. The handler function must be a coroutine function. It can be a regular
function or a method within a class. If it's a regular function, its first parameter is reserved, and you can assign it any name,
such as `self_handler`. If it's a method in a class, its second parameter is reserved (the first parameter is typically `self`),
and it can also be of any name.

This reserved parameter is automatically bound to the `HandlerCoroutine` object created by the handler, allowing you to access
the handler object within the handler. In this context, we'll use `self_handler` as an example. When calling the handler,
`self_handler` does not need to be passed as it is automatically generated.
