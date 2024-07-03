import pytest

from agere.commander import (
    CommanderAsync,
    Job,
    HandlerCoroutine,
    handler,
    tasker,
    PASS_WORD,
)
from agere.commander.edge import add_edge, add_conditional_edge


@pytest.fixture
def handler_example_1():
    @handler(PASS_WORD)
    async def _handler(self_handler):
        self_handler.data["nodes"].append("handler_1")
        self_handler.data["count"] += 1
        return "handler_2" if self_handler.data["count"] > 4 else "job_2"
    return _handler()


@pytest.fixture
def handler_example_2():
    @handler(PASS_WORD)
    async def _handler(self_handler) -> None:
        self_handler.data["nodes"].append("handler_2")
        self_handler.data["count"] += 1
    return _handler()


@pytest.fixture
def job_example_1():
    class JobExample(Job):
        @tasker(PASS_WORD)
        async def task(self):
            self.data["nodes"].append("job_1")
            self.data["count"] += 1
    return JobExample()


@pytest.fixture
def job_example_2():
    class JobExample(Job):
        @tasker(PASS_WORD)
        async def task(self):
            self.data["nodes"].append("job_2")
            self.data["count"] += 1
            return "job_1" if self.data["count"] % 3 == 0 else "handler_1"
    return JobExample()


@pytest.fixture
def data():
    return {"count": 0, "nodes": []}

@pytest.fixture
def commander():
    _commander = CommanderAsync()
    yield _commander
    _commander.exit()


def test_add_edge(
    commander: CommanderAsync,
    job_example_1: Job,
    handler_example_1,
    job_example_2: Job,
    handler_example_2,
    data: dict,
):
    # Setup
    job_example_1.data = data
    add_edge(from_node=job_example_1, to_node=handler_example_1, data=data)
    add_edge(from_node=handler_example_1, to_node=job_example_2, data=data)
    add_edge(from_node=job_example_2, to_node=handler_example_2, data=data)

    # Action
    commander.run_auto(job_example_1)

    # Assert
    assert data["nodes"] == ["job_1", "handler_1", "job_2", "handler_2"]
    assert data["count"] == 4


def test_add_conditional_edge(
    commander: CommanderAsync,
    job_example_1: Job,
    handler_example_1: HandlerCoroutine,
    job_example_2: Job,
    handler_example_2: HandlerCoroutine,
    data: dict,
):
    # Setup
    job_example_1.data = data
    map = {
        "job_1": job_example_1,
        "job_2": job_example_2,
        "handler_1": handler_example_1,
        "handler_2": handler_example_2,
    }
    add_edge(from_node=job_example_1, to_node=handler_example_1, data=data)
    add_conditional_edge(from_node=handler_example_1, map=map, data=data)
    add_conditional_edge(from_node=job_example_2, map=map, data=data)

    # Action
    commander.run_auto(job_example_1)

    # Assert
    assert data["nodes"] == ["job_1", "handler_1", "job_2", "job_1", "handler_1", "handler_2"]
    assert data["count"] == 6


def test_add_multiple_edges(
    commander: CommanderAsync,
    job_example_1: Job,
    handler_example_1: HandlerCoroutine,
    job_example_2: Job,
    handler_example_2: HandlerCoroutine,
    data: dict,
):
    # Setup
    job_example_1.data = data
    map = {
        "job_1": job_example_1,
        "job_2": job_example_2,
        "handler_1": handler_example_1,
        "handler_2": handler_example_2,
    }
    @handler(PASS_WORD)
    async def _handler(self_handler):
        self_handler.data["nodes"].append("handler_3")
    handler_example_3 = _handler()
    add_edge(from_node=job_example_1, to_node=handler_example_1, data=data)
    add_edge(from_node=job_example_1, to_node=handler_example_3, data=data)
    add_conditional_edge(from_node=handler_example_1, map=map, data=data)
    add_conditional_edge(from_node=job_example_2, map=map, data=data)

    # Action
    commander.run_auto(job_example_1)

    # Assert
    no_handler_3_chain = [node for node in data["nodes"] if node != "handler_3"]
    assert no_handler_3_chain == ["job_1", "handler_1", "job_2", "job_1", "handler_1", "handler_2"]
    assert len(data["nodes"]) == 8
