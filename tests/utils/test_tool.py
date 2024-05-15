import json
import pytest
from typing import TypedDict

from agere.utils.tool import (
    ToolsManager,
    tool,
    tool_kit,
    tool_parameter,
)
from agere.utils.tool_models import CustomToolModel, OpenaiToolModel
from agere.utils.tool import ToolsManagerInterface, ToolKit, ToolMetadata


kit_example = ToolKit()

@tool(description="The description for the tool.")
@tool_parameter(
    name="value",
    description="The description for the parameter of name.",
    default_value=1,
    choices=[1, 3, 5,7],
)
def tool_function_example(value: int = 1) -> int:
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


class ContextPiece(TypedDict):
    role: str
    content: str


def tool_bead_maker(tool_info: str) -> ContextPiece:
    return {
        "role": "system",
        "content": tool_info,
    }

def tool_token_counter(tool_info: str) -> int:
    return len(tool_info)

@pytest.fixture
def custom_tools_manager() -> ToolsManagerInterface:
    custom_tool_model = CustomToolModel(
        tool_bead_maker=tool_bead_maker,
    )
    return ToolsManager(tool_model=custom_tool_model)

@pytest.fixture
def openai_tools_manager() -> ToolsManagerInterface:
    openai_tool_model = OpenaiToolModel(
        tool_token_counter=tool_token_counter,
    )
    return ToolsManager(tool_model=openai_tool_model)

class TestTool:
    def test_tool_model_name(
        self,
        custom_tools_manager: ToolsManagerInterface,
        openai_tools_manager: ToolsManagerInterface
    ):
        # Assert
        assert custom_tools_manager.tool_model_name == "CUSTOM"
        assert openai_tools_manager.tool_model_name == "OPENAI"

    def test_tool_model_type(
        self,
        custom_tools_manager: ToolsManagerInterface,
        openai_tools_manager: ToolsManagerInterface
    ):
        # Assert
        assert custom_tools_manager.tool_model_type == "CUSTOM"
        assert openai_tools_manager.tool_model_type == "PROVIDED"

    def test_add_tool(self, custom_tools_manager: ToolsManagerInterface):
        # Action
        custom_tools_manager.add_tool(tool_function_example)
        custom_tools_manager.add_tool(kit_example, tool_type="PERMANENT")
        temporary_tools_names = [metadata.name for metadata in custom_tools_manager.get_tools_metadata(by_types=["TEMPORARY"])]
        permanent_tools_names = [metadata.name for metadata in custom_tools_manager.get_tools_metadata(by_types=["PERMANENT"])]

        # Assert
        assert set(temporary_tools_names) == {"tool_function_example"}
        assert set(permanent_tools_names) == {"tool_say_hello_example", "tool_say_goodbye_example"}
    
    def add_tools(
        self,
        openai_tools_manager: ToolsManagerInterface,
    ):
        # Action
        openai_tools_manager.add_tools(tools=[tool_function_example, ToolExample().tool_method_example])
        temporary_tools_names = [metadata.name for metadata in openai_tools_manager.get_tools_metadata(by_types=["TEMPORARY"])]

        # Assert
        assert set(temporary_tools_names) == {"tool_function_example", "tool_method_example"}

    def test_remove_tool(
        self,
        custom_tools_manager: ToolsManagerInterface,
    ):
        # Setup
        custom_tools_manager.add_tools(tools=[tool_function_example, ToolExample().tool_method_example])
        
        # Action
        custom_tools_manager.remove_tool(tool="tool_function_example")
        temporary_tools_names = [metadata.name for metadata in custom_tools_manager.get_tools_metadata(by_types=["TEMPORARY"])]
        
        # Assert
        assert set(temporary_tools_names) == {"tool_method_example"}
    
    def test_remove_tools(
        self,
        openai_tools_manager: ToolsManagerInterface,
    ):
        # Setup
        tool_example = ToolExample()
        openai_tools_manager.add_tools(
            tools=[tool_function_example, tool_example.tool_method_example, kit_example],
            tool_type="PERMANENT",
        )
        
        # Action
        openai_tools_manager.remove_tools(tools=[tool_example.tool_method_example, kit_example], tool_type="PERMANENT")
        permanent_tools_names = [metadata.name for metadata in openai_tools_manager.get_tools_metadata(by_types=["PERMANENT"])]
        
        # Assert
        assert set(permanent_tools_names) == {"tool_function_example"}

    def test_clear_tools(
        self,
        openai_tools_manager: ToolsManagerInterface,
    ):
        # Setup
        tool_example = ToolExample()
        openai_tools_manager.add_tools(
            tools=[tool_function_example, tool_example.tool_method_example, kit_example],
            tool_type="PERMANENT",
        )
        
        # Action
        openai_tools_manager.remove_tools(tools=[tool_example.tool_method_example, kit_example], tool_type="PERMANENT")
        openai_tools_manager.clear_tools(tool_type="PERMANENT")
        permanent_tools_names = [metadata.name for metadata in openai_tools_manager.get_tools_metadata(by_types=["PERMANENT"])]
        
        # Assert
        assert permanent_tools_names == []

    def test_register_tools(
        self,
        custom_tools_manager: ToolsManagerInterface,
    ):
        # Action
        custom_tools_manager.register_tools(tools=[tool_function_example, kit_example])
        
        # Assert
        assert set(custom_tools_manager.registered_tool_names) == {
            "tool_function_example",
            "tool_say_hello_example",
            "tool_say_goodbye_example",
        }

    def test_unregister_tools(
        self,
        openai_tools_manager: ToolsManagerInterface,
    ):
        # Setup
        openai_tools_manager.register_tools(tools=[tool_function_example, kit_example, ToolExample().tool_method_example])

        # Action
        openai_tools_manager.unregister_tools(tools=["tool_method_example", kit_example])

        # Assert
        assert openai_tools_manager.registered_tool_names == ["tool_function_example"]

    def test_clear_registered_tools(
        self,
        openai_tools_manager: ToolsManagerInterface,
    ):
        # Setup
        openai_tools_manager.register_tools(tools=[tool_function_example, kit_example, ToolExample().tool_method_example])

        # Action
        openai_tools_manager.unregister_tools(tools=["tool_method_example", kit_example])
        openai_tools_manager.clear_registered_tools()

        # Assert
        assert openai_tools_manager.registered_tool_names == []

    def test_all_tools_names(
        self,
        custom_tools_manager: ToolsManagerInterface,
    ):
        # Action
        custom_tools_manager.add_tool(tool_function_example, "PERMANENT")
        custom_tools_manager.add_tools([tool_function_example, ToolExample().tool_method_example], "TEMPORARY")

        # Assert
        assert set(custom_tools_manager.all_tools_names) == {
            "tool_function_example",
            "tool_method_example",
        }

        # Action
        custom_tools_manager.register_tools([kit_example, tool_function_example])

        # Assert
        assert set(custom_tools_manager.all_tools_names) == {
            "tool_function_example",
            "tool_method_example",
            "tool_say_hello_example",
            "tool_say_goodbye_example",
        }

    def test_create_tool_metadata(self, custom_tools_manager: ToolsManagerInterface):
        # Setup
        custom_tools_manager.add_tool(tool_function_example)

        # Action
        metadata = custom_tools_manager.create_tool_metadata(tool_function_example)

        # Assert
        assert isinstance(metadata, ToolMetadata)
        assert metadata.name == "tool_function_example"
        assert metadata.description == "The description for the tool."
        assert metadata.parameters == [
            {
                "name": "value",
                "description": "The description for the parameter of name.",
                "default_value": 1,
                "param_type": "string",
                "choices": [1, 3, 5,7],
                "required": True,
            },
        ]
        assert metadata.linked_tool == tool_function_example
        assert metadata.tool_kit is None

    def test_get_tools_metadata(self, openai_tools_manager: ToolsManagerInterface):
        # Setup
        openai_tools_manager.add_tool(tool_function_example, "PERMANENT")
        openai_tools_manager.register_tool(kit_example)

        # Action
        metadata_list = openai_tools_manager.get_tools_metadata(
            by_names=["tool_function_example", "tool_say_hello_example", "tool_method_example"],
        )

        # Assert
        assert len(metadata_list) == 2
        assert {metadata.name for metadata in metadata_list} == {"tool_function_example", "tool_say_hello_example"}

    def test_get_tools_metadata_by_names(self, openai_tools_manager: ToolsManagerInterface):
        # Setup
        openai_tools_manager.add_tool(tool_function_example, "PERMANENT")
        openai_tools_manager.register_tool(kit_example)

        # Action
        metadata_list = openai_tools_manager.get_tools_metadata_by_names(
            names=["tool_function_example", kit_example],
        )

        # Assert
        assert len(metadata_list) == 3
        assert {metadata.name for metadata in metadata_list} == {
            "tool_function_example",
            "tool_say_hello_example",
            "tool_say_goodbye_example",
        }

    def test_get_tools_manual(
        self,
        custom_tools_manager: ToolsManagerInterface,
        openai_tools_manager: ToolsManagerInterface,
    ):
        # Setup
        custom_tools_manager.add_tools([tool_function_example, ToolExample().tool_method_example])
        custom_tools_manager.add_tool(kit_example, "PERMANENT")
        openai_tools_manager.add_tool(kit_example)
        openai_tools_manager.add_tools([ToolExample.tool_method_example, tool_function_example], "PERMANENT")
        openai_tools_manager.register_tool(tool_function_example)

        # Action
        manual_for_custom = custom_tools_manager.get_tools_manual()
        manual_for_openai = openai_tools_manager.get_tools_manual(
            by_types=["TEMPORARY"],
            by_names=["tool_function_example"],
        )

        # Assert
        assert isinstance(manual_for_custom, str)
        assert manual_for_custom
        assert isinstance(manual_for_openai, list)
        assert len(manual_for_openai) == 3

    def test_get_linked_tool(self, custom_tools_manager: ToolsManagerInterface):
        # Setup
        custom_tools_manager.add_tool(tool_function_example)

        # Action
        callable_tool = custom_tools_manager.get_linked_tool("tool_function_example")

        # Assert
        assert callable_tool(2) == 2

    def test_wrap_tools_to_bead(
        self,
        custom_tools_manager: ToolsManagerInterface,
        openai_tools_manager: ToolsManagerInterface,
    ):
        # Setup
        custom_tools_manager.add_tool(tool_function_example, "PERMANENT")
        custom_tools_manager.add_tool(ToolExample().tool_method_example, "TEMPORARY")
        custom_tools_manager.register_tool(kit_example)
        openai_tools_manager.add_tool(tool_function_example)

        # Action
        metadata_list = custom_tools_manager.get_tools_metadata(by_types=["PERMANENT"], by_names=["tool_say_hello_example"])
        bead = custom_tools_manager.wrap_tools_to_bead(tools=metadata_list)  # type: ignore
        tool_bead_piece = bead[0]

        # Assert
        assert len(metadata_list) == 2
        assert isinstance(tool_bead_piece, dict)
        assert tool_bead_piece.get("role") == "system"
        with pytest.raises(AssertionError):
            openai_tools_manager.wrap_tools_to_bead(tools=[tool_function_example])

    def test_tools_manual_token_num(
        self,
        custom_tools_manager: ToolsManagerInterface,
        openai_tools_manager: ToolsManagerInterface,
    ):
        # Setup
        custom_tools_manager.add_tool(tool_function_example)
        openai_tools_manager.add_tool(tool_function_example)

        # Action
        manual = openai_tools_manager.get_tools_manual(by_names=["tool_function_example"])
        
        # Assert
        assert openai_tools_manager.tools_manual_token_num(
            by_names=["tool_function_example"],
        ) == len(str(manual))
        with pytest.raises(AssertionError):
            custom_tools_manager.tools_manual_token_num(by_names=["tool_function_example"])

    async def test_custom_parse_response(
        self,
        custom_tools_manager: ToolsManagerInterface,
        async_custom_llm_response_fixture,
    ):
        # Action
        make_role_generator = await custom_tools_manager.parse_response(async_custom_llm_response_fixture)
        to_user_gen = make_role_generator("to_user")
        function_call_gen = make_role_generator("tool_call")
        to_user_list = []
        function_call_list = []
        async for to_user in to_user_gen:
            to_user_list.append(to_user)
        async for function_call in function_call_gen:
            function_call_list.append(function_call)

        # Assert
        assert ''.join(to_user_list) == ''.join(
            [
                "Turning off ",
                "the light for you.",
                "Checking the weather for you, please wait.",
            ],
        )
        function_call_list_check = [
            {
                "name": "light_off",
                "parameters": {},
            },
            {
                "name": "get_weather",
                "parameters": {
                    "position": "Hangzhou",
                    "unit": "celsius",
                }
            },
        ]
        for i in range(2):
            assert json.loads(function_call_list[i]) == function_call_list_check[i]

    async def test_openai_parse_response(
        self,
        openai_tools_manager: ToolsManagerInterface,
        async_openai_response_fixture,
    ):
        # Action
        make_role_generator = await openai_tools_manager.parse_response(async_openai_response_fixture)
        to_user_gen = make_role_generator("to_user")
        function_call_gen = make_role_generator("tool_call")
        to_user_list = []
        function_call_list = []
        async for to_user in to_user_gen:
            to_user_list.append(to_user)
        async for function_call in function_call_gen:
            function_call_list.append(function_call)

        # Assert
        assert ''.join(to_user_list) == ''.join(
            [
                'I am search \\"weather\\" for you.',
                '\n',
                'I am search weather in Beijing.',
            ],
        )
        function_call_list_check = [
            {
                "tool_call_index": 0,
                "tool_call_id": "call_vM7ZCfu7VF0curI2YwIpCNVh",
                "name": "get_current_weather",
                "arguments": {"location": "Paris"},
            },
            {
                "tool_call_index": 1,
                "tool_call_id": "call_AOefM0a9RMWTiJmOSDsW2mZM",
                "name": "get_current_weather",
                "arguments": {"location": "Beijing", "unit": "celsius"}
            },
        ]
        for i in range(2):
            assert json.loads(function_call_list[i]) == function_call_list_check[i]
