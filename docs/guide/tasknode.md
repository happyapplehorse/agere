When using Agere to build an agent, you only need to consider what the current task is and what the next task will be.
Once you define each task, run a commander and add the tasks to it. The commander will automatically schedule and execute
these tasks for you.

TaskNode is the basic unit of the task flow. Each small task is a `TaskNode`. When a new task arises, it is attached to
a `TaskNode` (usually the one that generated the task) and becomes a child node of that `TaskNode`. Each node has one parent
node and several child nodes. When all the child nodes of a node are completed, the node itself also becomes completed.
`TaskNode` can have callbacks attached; you can use callbacks to perform different actions at different states of the task.

`TaskNode` includes `handler`, `Job`, and `commander(CommanderAsync)`. `Job` and `handler` are used to define specific
task nodes, while `commander` is used to manage and schedule these nodes. `commander` is a special `TaskNode`, usually the root
node of all nodes.
