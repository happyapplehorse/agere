import pytest
from typing import TypedDict

from agere.utils.tool_models import CustomToolModel, OpenaiToolModel
from agere.utils.tool import ToolsManager, ToolsManagerInterface


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
