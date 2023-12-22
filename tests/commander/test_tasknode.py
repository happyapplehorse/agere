import pytest
from unittest.mock import Mock, AsyncMock

from agere.commander._commander import TaskNode


def test_ancestor_chain():
    # Setup
    tasknode_1 = TaskNode()
    tasknode_2 = TaskNode()
    tasknode_3 = TaskNode()
    tasknode_4 = TaskNode()
    tasknode_5 = TaskNode()

    # Action
    tasknode_1._parent = "Null"
    tasknode_1.add_child(tasknode_2)
    tasknode_2.add_child(tasknode_3)
    tasknode_2.add_child(tasknode_4)
    tasknode_3.add_child(tasknode_5)

    # Assert
    assert tasknode_5.ancestor_chain == [tasknode_5, tasknode_3, tasknode_2, tasknode_1]
    assert tasknode_4.ancestor_chain == [tasknode_4, tasknode_2, tasknode_1]
    
async def test_terminate_task_node():
    # Setup
    tasknode = TaskNode()
    tasknode._children.extend([Mock(), Mock()])
    tasknode_parent = Mock()
    tasknode_parent.del_child = AsyncMock()
    tasknode._parent = tasknode_parent
    commander = Mock()
    commander._callback_handle = AsyncMock()
    tasknode._commander = commander
    callback = Mock()
    tasknode._callback = callback

    # Action
    await tasknode.terminate_task_node()
    
    # Assert
    assert tasknode._children == []
    assert tasknode.state == "TERMINATED"
    tasknode_parent.del_child.assert_called_with(tasknode)
    commander._callback_handle.assert_called_with(
        callback=callback,
        which="at_terminate",
        task_node=tasknode,
    )

async def test_close_task_node():
    # Setup
    tasknode_1 = TaskNode()
    tasknode_2 = TaskNode()
    tasknode_3 = TaskNode()
    tasknode_4 = TaskNode()
    tasknode_5 = TaskNode()
    tasknode_6 = TaskNode()
    commander = Mock()
    commander._callback_handle = AsyncMock()
    tasknode_2._commander = commander
    callback = Mock()
    tasknode_2._callback = callback

    # Action
    tasknode_1._parent = "Null"
    tasknode_1.add_child(tasknode_2)
    tasknode_2.add_child(tasknode_3)
    tasknode_3.add_child(tasknode_4)
    tasknode_3.add_child(tasknode_5)
    tasknode_5.add_child(tasknode_6)
    await tasknode_2.close_task_node()

    # Assert
    assert tasknode_2.children == []
    assert tasknode_2 not in tasknode_1.children
    assert tasknode_2.state == "TERMINATED"
    assert tasknode_3.state == "TERMINATED"
    assert tasknode_4.state == "TERMINATED"
    assert tasknode_5.state == "TERMINATED"
    assert tasknode_6.state == "TERMINATED"
    commander._callback_handle.assert_called_with(
        callback=callback,
        which="at_terminate",
        task_node=tasknode_2,
    )

