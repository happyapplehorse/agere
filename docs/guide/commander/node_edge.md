# Node-Edge Pattern
Agere is very flexible, and you can use the node+edge pattern to construct workflows.
You can create various custom edge types through callbacks.

Defining an edge is simple, and here is an example code for `add_edge`:
```python
from agere.commander._commander import Job, HandlerCoroutine


def add_edge(
    from_node: Job | HandlerCoroutine,
    to_node: Job | HandlerCoroutine,
    data: Any | None = None,
) -> None:
    """To add a simple edge between two nodes.

    The simple edge ensures that the next node is automatically executed after the previous node has completed.

    Args:
        from_node: The previous node.
        to_node: The next node.
        data: Shared data, which allows each node to access data from this object.
    """
    async def next_node(from_node: Job | HandlerCoroutine, to_node: Job | HandlerCoroutine) -> None:
        # This is important; it allows a completed node to be ready again so that it can run multiple times.
        if to_node not in to_node.children:
            to_node._children.append(to_node)

        if isinstance(to_node, Job):
            await from_node.put_job(to_node, parent=from_node.commander)
        elif isinstance(to_node, HandlerCoroutine):
            # This is important; it allows a handler object (coroutine object) to run multiple times.
            to_node.reusable = True
            from_node.call_handler(to_node, parent=from_node.commander)
        else:
            assert False, "The connected node should be a Job or handler object."

    if isinstance(from_node, HandlerCoroutine):
        from_node.reusable = True

    if data is not None:
        to_node.data = data

    from_node.add_callback_functions(
        which="at_job_end" if isinstance(from_node, Job) else "at_handler_end",
        functions_info={
            "function": next_node,
            "params": {
                "args": (from_node, to_node),
                "kwargs": {},
            },
        },
    )
```
You can customize your required edge types following this method.

## Simple Edges and Conditional Edges

Currently, Agere offers two pre-set common edge types: `add_edge` and `add_conditional_edge`.

`add_edge` adds a simple edge between two nodes. After the preceding node completes execution,
the following node will automatically execute. Its function signature is
`add_edge(from_node: Job | HandlerCoroutine, to_node: Job | HandlerCoroutine, data: Any | None = None)`.
`from_node` is the previous node, `to_node` is the next node, and `data` is optional. If specified,
it will bind to the node's `data` attribute and can be directly accessed within the node.
It serves as a context variable for passing information between nodes, allowing each node to store and
retrieve information from this object.

!!! note
    `data` is only bound to the node directed by each edge; therefore, the initial node should manually
    configure resources, like `init_node.data=data`.

`add_conditional_edge` adds a conditional edge between two nodes. After the preceding node completes its
execution, based on its return value, the conditional edge selects the appropriate next node to execute.
Its function signature is
`add_conditional_edge(from_node: Job | HandlerCoroutine, map: dict[str, Job | HandlerCoroutine], data: Any | None = None)`.
`from_node` is the preceding node, and `map` is a dictionary storing the next nodes corresponding to
different outcomes of the preceding node. `data` is a resource object.

!!! note
    data is only bound to the node directed by each edge; therefore, the initial node should manually
    configure resources, like `init_node.data=data`.


## Multiple Edges
You can add multiple edges to the same node, allowing them to execute simultaneously. For example,
define the following nodes:
```python
from agere.commander import (
    CommanderAsync,
    Job,
    HandlerCoroutine,
    handler,
    tasker,
    PASS_WORD,
)
from agere.commander.edge import add_edge, add_conditional_edge


@handler(PASS_WORD)
async def handler_1(self_handler):
    self_handler.data["nodes"].append("handler_1")
    self_handler.data["count"] += 1
    return "handler_2" if self_handler.data["count"] > 4 else "job_2"

@handler(PASS_WORD)
async def handler_2(self_handler) -> None:
    self_handler.data["nodes"].append("handler_2")
    self_handler.data["count"] += 1

@handler(PASS_WORD)
async def handler_3(self_handler):
    self_handler.data["nodes"].append("handler_3")

class Job1(Job):
    @tasker(PASS_WORD)
    async def task(self):
        self.data["nodes"].append("job_1")
        self.data["count"] += 1

class Job2(Job):
    @tasker(PASS_WORD)
    async def task(self):
        self.data["nodes"].append("job_2")
        self.data["count"] += 1
        return "job_1" if self.data["count"] % 3 == 0 else "handler_1"
```
Then add the following edge configurations:
```python
job_1 = Job1()
job_2 = Job2()
handler_1 = handler_1()
handler_2 = handler_2()
handler_3 = handler_3()

job_1.data = data  # Set resources for the initial node
map = {
    "job_1": job_1,
    "job_2": job_2,
    "handler_1": handler_1,
    "handler_2": handler_2,
}

add_edge(from_node=job_1, to_node=handler_1, data=data)
add_edge(from_node=job_1, to_node=handler_3, data=data)
add_conditional_edge(from_node=handler_1, map=map, data=data)
add_conditional_edge(from_node=job_2, map=map, data=data)
```
Finally, run this example:
```python
commander.run_auto(job_1) 
```
Thus, the execution process will look as follows:
<figure markdown>
  ![node-edge pattern](https://raw.githubusercontent.com/happyapplehorse/happyapplehorse-assets/main/agere/node_edge_example_1.png){ width="400" }
  <figcaption>Multiple edges executed simultaneously.</figcaption>
</figure>
<figure markdown>
  ![node-edge pattern](https://raw.githubusercontent.com/happyapplehorse/happyapplehorse-assets/main/agere/node_edge_example_2.png){ width="400" }
  <figcaption>Multi-path workflow.</figcaption>
</figure>
