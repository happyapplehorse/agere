import pytest

from agere.commander import Callback
from agere.commander._commander import TaskNode


@pytest.fixture
def callback():
    return Callback()


def test_task_node_setter():
    # Setup
    tasknode_1 = TaskNode()
    tasknode_2 = TaskNode()
    tasknode_3 = TaskNode()
    tasknode_4 = TaskNode()
    tasknode_5 = TaskNode()
    tasknode_1.id = "1"
    tasknode_2.id = "2"
    tasknode_3.id = "3"
    tasknode_4.id = "4"
    tasknode_5.id = "5"

    callback_1 = Callback()
    callback_2 = Callback(task_node_auto_lock_num=3)
    callback_3 = Callback(task_node=TaskNode(), task_node_auto_lock_num=3)

    # Action
    callback_1._task_node = tasknode_1
    callback_1._task_node = tasknode_2
    callback_1._task_node = tasknode_3
    callback_1._task_node = tasknode_4
    callback_1._task_node = tasknode_5
    callback_2._task_node = tasknode_1
    callback_2._task_node = tasknode_2
    callback_2._task_node = tasknode_3
    callback_2._task_node = tasknode_4
    callback_2._task_node = tasknode_5
    callback_3._task_node = tasknode_1
    callback_3._task_node = tasknode_2
    callback_3._task_node = tasknode_3
    callback_3._task_node = tasknode_4
    callback_3._task_node = tasknode_5

    # Assert
    assert callback_1.task_node is not None
    assert callback_1.task_node.id == "5"
    assert callback_2.task_node is not None
    assert callback_2.task_node.id == "3"
    assert callback_3.task_node is not None
    assert callback_3.task_node.id == "2"
