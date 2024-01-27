Commander is used for automatic management and execution of tasks. Each commander has an asynchronous queue and is
managed by a commander loop. For thread safety, there is only one commander loop under each commander. If you need
to add tasks outside of the thread, use thread-safe methods like `put_job_threadsafe` or `call_handler_threadsafe`.
You can also use these methods to coordinate among multiple commanders, but this is usually unnecessary.

!!! note

When instantiating a commander, you can set your logger through the `logger` parameter.


On launching a commander, you can set the initial Job, which can be a single Job or a sequence of Jobs (list,
tuple, etc.). The commander will immediately start executing these Jobs after running. The `CommanderAsync.run`
method can have a return value. By default, it returns `None` when the commander ends. However, it will return the
value specified by `return_result` when using the `CommanderAsync.exit` method or the `exit_commander` method of
Job and handler.

!!! note

Once a commander is launched, it immediately runs in a commander loop. This means that `CommanderAsync.run` will
block the current thread until the commander exits.


Attempting to launch a commander that is already running will raise a `CommanderAlreadyRunningError`, and submitting
tasks to a commander that has not started will raise a `CommanderNotRunError`.
You can also use `run_auto` to start a commander and add tasks. It will automatically start the commander and run
tasks if the commander is not running. If the commander is already running, it will add the tasks to the running commander.


Both `run` and `run_auto` can take an `auto_exit` parameter. If set to True, it will automatically end the commander
after all tasks (including jobs and handlers) are completed.


Using the `run_auto` method to start a commander can automatically determine the running state of the commander and is safer,
but it has the disadvantage of unpredictability in terms of whether the current thread will be blocked. If the commander is
not running, it will start the commander and block the current thread. If the commander is already running, it will add the
task to the current commander and return immediately. This means that you might not be able to clearly determine where the
commander loop is running or which thread is being blocked by the commander loop. Therefore, it's generally recommended to
use `run` for manual management of the commander loop. You can start the commander at the beginning of the program and manually
close it at the end.


You can use the `running_status` property to check whether the commander is running (or has started). The `is_empty` method
returns whether the commander is empty; it returns True when there are no running or pending jobs and handlers in the commander,
otherwise False.


To manually end the commander, you can use the `exit` method. It takes two parameters: `return_result` and `wait`. Through the
`return_result` parameter, you can specify the return value for the run method. When `wait` is set to `True`, the method will
wait until the commander truly ends, otherwise, it returns immediately.


You can use `wait_for_exit` to wait for the commander to end. It doesn’t actively end the commander but passively waits until
the commander ends before returning.


To add tasks from outside the commander loop (in a new thread), you can use `put_job_threadsafe` or `call_handler_threadsafe`.
Generally, you are always submitting new Jobs or initiating new handlers inside a Job or handler, which is always thread-safe,
and you can use methods provided by the Job or handler itself, referring to Job and handler.
