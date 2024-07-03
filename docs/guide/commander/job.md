A job is a packaging of resources and actions for a task, scheduled through the commander's task queue.
This ensures sequencing, where a job submitted earlier will always be executed first. You can consider
it as submitting a task to a superior. It is generally more suitable than a handler when dealing with
tasks that have a circular structure.


To define a Job, you need to import `Job` from `agere.commander` and inherit it, implementing the required `task` method.
The `task` method describes the specific tasks that the job needs to perform. In the task, you can execute the specific
logic of the Job or return a handler.


You should be careful with time-consuming operations that block the thread. These should not be placed directly in the task,
as they will block the commander loop. It is important to note that although the task can be a coroutine function,
the commander cannot schedule a new Job until the Job's `task` is completed. This means that if a Job takes a long time to
complete or needs to be waited upon, it can hinder other Jobs from being started. The solution to this problem is to call a
handler within the Job to perform the task or directly return it as a handler.


The task must be decorated with the `tasker` decorator, and the `tasker` decorator requires a password. Its content is
(currently) `"I assure all time-consuming tasks are delegated externally"`. This is just to remind you not to place
time-consuming tasks in the task to avoid blocking the commander. Of course, you don’t need to actually input this password;
you just need to import `PASS_WORD` from `agere.commander` and use it.
