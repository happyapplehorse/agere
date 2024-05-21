from typing import Any

from ._commander import Job, HandlerCoroutine


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

def add_conditional_edge(
    from_node: Job | HandlerCoroutine,
    map: dict[str, Job | HandlerCoroutine],
    data: Any | None = None,
) -> None:
    """Add a conditional edge between two nodes.

    The conditional edge automatically selects the corresponding next node to execute from the map
    dictionary based on the execution result of the previous node.

    Args:
        from_node: The previous node.
        map:
            The mapping dictionary stores the next nodes corresponding to different results of the
            previous node.
        data: Shared data, which allows each node to access data from this object.
    """
    async def next_node(
        from_node: Job | HandlerCoroutine,
        map: dict[Any, Job | HandlerCoroutine],
    ) -> None:
        result = from_node.result
        to_node = map.get(result)
        if to_node is None:
            return
        
        # This is important; it allows a completed node to be ready again so that it can run multiple times.
        if to_node not in to_node.children:
            to_node._children.append(to_node)
        
        if data is not None:
            to_node.data = data
        
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
    
    from_node.add_callback_functions(
        which="at_job_end" if isinstance(from_node, Job) else "at_handler_end",
        functions_info={
            "function": next_node,
            "params": {
                "args": (from_node, map),
                "kwargs": {},
            },
        },
    )
