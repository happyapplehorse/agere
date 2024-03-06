# Agere

<p align="center">
    <img src="https://raw.githubusercontent.com/happyapplehorse/happyapplehorse-assets/main/imgs/agere_logo_transparent.png" alt="Logo">
</p>

Agere is a lightweight framework for building agents, with no third-party dependencies. Its features are universality and complete customizability.
It simplifies the process of building agents with complex logic by breaking down a complicated workflow into a series of independent, small steps,
which also facilitates future expansion or modification of its functionalities.

Agere utilizes a model of 'node-edge' to construct workflows. 
Tasks are divided into 'node-edge'—nodes connected by edges, grouping each node with its subsequent actions.
One of the benefits of using edge nodes is that it makes the logic more coherent; when you define a node, you also specify the following edge.
Another advantage is that it allows for more direct and flexible parameter transmission between different nodes. You can pass any form of parameters as needed directly
in the call without having to use a unified context variable. Additionally, implementing conditional edges becomes simpler and more straightforward.

Agere employs Jobs and handlers as the basic types of task nodes. By defining Jobs (classes) and handlers (functions or methods), it breaks down the various parts of
an agent. The nodes are reusable and also facilitate future expansions or modifications of functionalities.
Within a Job, you can submit new Jobs or call handlers.
In handlers, you can also call other handlers or submit Jobs. Both Jobs and handlers fall under the category of TaskNode, i.e., task nodes, forming a tree structure that
tracks the relationships and running states of tasks. Within these nodes, you can add callbacks to execute at different times, such as at the start or end of a task,
upon encountering errors, or when being terminated, among others.

In constructing workflows, Agere possesses the following features:
- **Multitasking**: Agere enables multiple tasks to run in parallel. 
- **Strategic Timing**: Task states at different moments can be controlled through callbacks. 
- **Branching Out**: Different states of a node can be linked, for example, connecting edges to a node's start, end, or termination states. 
- **Tailor-made**: The passing of parameters between nodes is more flexible, with each node being able to customize parameter transmission.

Agere emphasizes universality, operating independently of any tools, specific interfaces, or forms, and is not coupled with any tool. This allows it to invoke any
tool easily, facilitating smooth collaboration and integration with other tools.
