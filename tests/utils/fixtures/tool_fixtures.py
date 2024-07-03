import pytest

from agere.utils.tool import (
    ToolKit,
    tool,
    tool_kit,
    tool_parameter,
)


kit_example = ToolKit()

@tool(description="The description for the tool.")
@tool_parameter(
    name="value",
    description="The description for the parameter of name.",
    default_value=1,
    choices=[1, 3, 5,7],
)
def tool_function_example_(value: int = 1) -> int:
    return value

@tool(description="This is a example tool which says hello to someone.")
@tool_kit(
    kit=kit_example,
    description="The description for the kit."
)
@tool_parameter(
    name="name",
    description="The name to say hello."
)
def tool_say_hello_example(name: str) -> str:
    return f"Hi, {name}!"

@tool
@tool_kit(kit=kit_example)
def tool_say_goodbye_example(name: str) -> str:
    """This is a example tool which says goodbye to someone.

    Args:
        name (str): The name to say goodbye.
    """
    return f"Goodbye, {name}"

class ToolExample:
    @tool
    @tool_parameter(
        name="value2",
        description="The second value.",
        default_value=2,
    )
    def tool_method_example(self, value1: int, value2: int = 0) -> int:
        """This is a tool example which is a class method.

        This tool return the addition of the given two value.

        Args:
            value1 (int): The first value.
            value2 (int): The second value.
        """
        return value1 + value2

@pytest.fixture
def tool_function_example():
    tool = tool_function_example_
    tool.__name__ = "tool_function_example"
    return tool_function_example_

@pytest.fixture
def tool_method_example():
    return ToolExample().tool_method_example

@pytest.fixture
def tool_kit_example():
    return kit_example
