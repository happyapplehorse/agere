Agere provides callbacks for different stages of tasks, and each task node can have its own callback. There are seven types
of callbacks:

1. `at_job_start`  
Executed at the start of a job.

2. `at_handler_start`  
Executed at the start of a handler.

3. `at_exception`  
Executed when a job or handler encounters an exception.

4. `at_terminate`  
Executed when a job or handler is terminated.

5. `at_handler_end`  
Executed at the end of a handler.

6. `at_job_end`  
Executed at the end of a job.

7. `at_commander_end`  
Executed at the end of the commander.


There are multiple ways to add callbacks. Here, we'll introduce the use of the `add_callback_functions` method, which takes
`which` and `functions_info` as parameters. `which` must be one of the callback types mentioned above, and `functions_info`
is a dictionary representing callback function information. If there are multiple callback functions, this parameter can
also be a list. A function information dictionary typically has the following structure:
```python
{
    "function": callback_function,
    "params": {
        "args": position arguments of callback function,
        "kwargs": key-values arguments of callback function
    },
    "inject_task_node": bool, whether to pass back the task node into the callback function automatically
}
```

Both `params` and `inject_task_node` are optional. `params` is used to specify the parameters of the callback function.
When `inject_task_node` is set to `True`, the callback function will receive the `task_node` as a keyword argument,
representing the task node to which the callback belongs.
