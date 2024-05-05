from collections.abc import Callable
from typing import Literal, Any, AsyncGenerator

from tool_models._custom_tool_model import CustomToolModel
from ._tool_base import (
    CustomToolModelInterface,
    ProvidedToolModelInterface,
    ToolsManagerInterface,
    ToolModelInterface,
    ToolMetadata,
)
from ._exceptions import AgereUtilsError


class ToolError(AgereUtilsError):
    """Raised when encountering an error related to the tool."""


class ToolKit:
    def __init__(self):
        self.description: str = ""
        self.tools: list[Callable] = []

    def __iter__(self):
        return iter(self.tools)

    def add_tools(self, tools: list[Callable]) -> None:
        self.tools.extend(tools)

    def set_description(self, description: str) -> None:
        self.description = description
    

def tool(description: str):
    """Decorator for a tool."""

    def decorator(func):
        func.__tool__ = True
        func.__tool_description__ = description
        if not hasattr(func, "__tool_parameters__"):
            func.__tool_parameters__ = []
        return func
    
    return decorator

def tool_kit(tool_kit_name: str, tool_kit_description: str | None = None):
    """Decorator for a tool.
    
    Add the tool into a tool kit.
    """
    
    def decorator(func):
        func.__tool_kit__ = tool_kit_name

        global_name_space = globals()
        if tool_kit_name not in global_name_space:
            global_name_space[tool_kit_name] = ToolKit()
        tool_kit = global_name_space[tool_kit_name]

        if tool_kit_description is not None:
            tool_kit.description = tool_kit_description
        tool_kit.tools.append(func)
        
        return func
    
    return decorator

def tool_parameter(
    *,
    name: str,
    description: str,
    default_value: str = "",
    param_type: str = "string",
    choices: list | None = None,
    required: bool = True,
):
    """Decorator for tool parameters.

    Args:
        name: The name of the tool parameter.
        description: The description of the tool parameter.
        default_value: The default value of the tool parameter.
        type: The type of the tool parameter.
        required: Whether the tool parameter is required.
    """
    def decorator(func):
        if not hasattr(func, "__tool_parameters__"):
            func.__tool_parameters__ = []
        func.__tool_parameters__.append(
            {
                "name": name,
                "description": description,
                "default_value": default_value,
                "param_type": param_type,
                "choices": choices,
                "required": required,
            }
        )
        return func

    return decorator


class ToolsManager(ToolsManagerInterface):
   
    def __init__(self, tool_model: ToolModelInterface):
        self._tool_model = tool_model
        self._permanent_tools: dict[str, ToolMetadata] = {}
        self._temporary_tools: dict[str, ToolMetadata] = {}
        self._registered_tools: dict[str, ToolMetadata] = {}
    
    @property
    def tool_model_name(self) -> str:
        return self.tool_model.tool_model_name
    
    @property
    def tool_model_type(self) -> Literal["CUSTOM", "PROVIDED"]:
        if isinstance(self._tool_model, CustomToolModelInterface):
            return "CUSTOM"
        elif isinstance(self._tool_model, ProvidedToolModelInterface):
            return "PROVIDED"
        else:
            assert False

    @property
    def tool_model(self) -> ToolModelInterface:
        return self._tool_model

    @tool_model.setter
    def tool_model(self, value: ToolModelInterface):
        self._tool_model = value

    def add_tool(self, tool: Callable, tool_type: Literal["PERMANENT", "TEMPORARY"] = "TEMPORARY") -> None:
        self._validate_tool(tool)
        if tool_type == "PERMANENT":
            self._permanent_tools[tool.__name__] = self.create_tool_metadata(tool)
        if tool_type == "TEMPORARY":
            self._temporary_tools[tool.__name__] = self.create_tool_metadata(tool)
    
    def add_tools(self, tools: list[Callable], tool_type: Literal["PERMANENT", "TEMPORARY"] = "TEMPORARY") -> None:
        for tool in tools:
            self.add_tool(tool, tool_type=tool_type)
    
    def remove_tool(self, tool: Callable | str, tool_type: Literal["PERMANENT", "TEMPORARY"] = "TEMPORARY") -> None:
        if isinstance(tool, str):
            if tool_type == "PERMANENT":
                self._permanent_tools.pop(tool, None)
            if tool_type == "TEMPORARY":
                self._temporary_tools.pop(tool, None)
            return
        self._validate_tool(tool)
        if tool_type == "PERMANENT":
            self._permanent_tools.pop(tool.__name__, None)
        if tool_type == "TEMPORARY":
            self._temporary_tools.pop(tool.__name__, None)
    
    def remove_tools(self, tools: list[Callable | str], tool_type: Literal["PERMANENT", "TEMPORARY"] = "TEMPORARY") -> None:
        for tool in tools:
            self.remove_tool(tool, tool_type=tool_type)
    
    def clear_tools(self, tool_type: Literal["PERMANENT", "TEMPORARY"] = "TEMPORARY") -> None:
        if tool_type == "PERMANENT":
            self._permanent_tools = {}
        if tool_type == "TEMPORARY":
            self._temporary_tools = {}
    
    def register_tool(self, tool: Callable) -> None:
        self._validate_tool(tool)
        self._registered_tools[tool.__name__] = self.create_tool_metadata(tool)
    
    def register_tools(self, tools: list[Callable]) -> None:
        for tool in tools:
            self.remove_tool(tool)
    
    def unregister_tools(self, tools: list[Callable | str]) -> None:
        for tool in tools:
            if isinstance(tool, str):
                self._registered_tools.pop(tool, None)
                return
            self._validate_tool(tool)
            self._registered_tools.pop(tool.__name__, None)

    def clear_registered_tools(self) -> None:
        self._registered_tools = {}

    @property
    def registered_tool_names(self) -> list[str]:
        return list(self._registered_tools.keys())

    @property
    def all_tools_names(self) -> list[str]:
        result = set()
        result.update(self._permanent_tools.keys())
        result.update(self._temporary_tools.keys())
        result.update(self._registered_tools.keys())
        return list(result)

    def create_tool_metadata(self, tool: Callable) -> ToolMetadata:
        self._validate_tool(tool)
        tool_metadata = ToolMetadata(
            name = tool.__tool_parameters__["name"],
            description = tool.__tool_description__,
            parameters = tool.__tool_parameters__,
            linked_tool = tool,
        )
        return tool_metadata
    
    def get_tools_metadata(
        self,
        by_types: list[Literal["PERMANENT", "TEMPORARY"]] | Literal["ALL"] = "ALL",
        by_names: list[str] | None = None,
    ) -> list[ToolMetadata]:
        tool_names = set()
        by_types = ["PERMANENT", "TEMPORARY"] if by_types == "ALL" else by_types
        if "PERMANENT" in by_types:
            tool_names.update(self._permanent_tools.keys())
        if "TEMPORARY" in by_types:
            tool_names.update(self._temporary_tools.keys())
        if by_names:
            tool_names.update(by_types)
        return self.get_tools_metadata_by_names(list(tool_names))

    def get_tools_metadata_by_names(self, names: list[str]) -> list[ToolMetadata]:
        result = []
        for name in names:
            if name in self._registered_tools:
                result.append(self._registered_tools[name])
                continue
            if name in self._temporary_tools:
                result.append(self._temporary_tools[name])
                continue
            if name in self._permanent_tools:
                result.append(self._permanent_tools[name])
                continue
        return result

    def get_tools_manual(
        self,
        by_types: list[Literal["PERMANENT", "TEMPORARY"]] | Literal["ALL"] = "ALL",
        by_names: list[str] | None = None,
    ) -> Any:
        tools = self.get_tools_metadata(by_types=by_types, by_names=by_names)
        return self.tool_model.get_tools_manual(tools=tools)

    def get_linked_tool(self, tool_name: str) -> Callable:
        if tool_name in self._registered_tools:
            linked_tool = self._registered_tools[tool_name]
            return linked_tool.linked_tool
        if tool_name in self._temporary_tools:
            linked_tool = self._temporary_tools[tool_name]
            return linked_tool.linked_tool
        if tool_name in self._permanent_tools:
            linked_tool = self._permanent_tools[tool_name]
            return linked_tool.linked_tool
        raise ValueError(f"There is no corresponding tool for '{tool_name}'.")

    def wrap_tools_to_bead(self, tools: list[ToolMetadata | Callable]) -> list:
        assert isinstance(self.tool_model, CustomToolModelInterface), (
            "The method 'wrap_tools_to_bead' should only be used when utilizing "
            "a CustomToolModelInterface type of tool model."
        )
        tools_metadata_list = [tool if isinstance(tool, ToolMetadata) else self.create_tool_metadata(tool) for tool in tools]
        description = self.tool_model.get_tools_manual(tools_metadata_list)
        tool_bead = self.tool_model.tool_manual_bead_maker(description)
        return [tool_bead]

    def tools_manual_token_num(
        self,
        by_types: list[Literal["PERMANENT", "TEMPORARY"]] | Literal["ALL"] = "ALL",
        by_names: list[str] | None = None,
    ) -> int:
        assert isinstance(self.tool_model, ProvidedToolModelInterface), (
            "The method 'tools_manual_token_num' should only be used when utilizing "
            "a ProvidedToolModelInterface type of tool model."
        )
        tools_metadata = self.get_tools_metadata(by_types=by_types, by_names=by_names)
        return self.tool_model.tool_manual_token_counter(tools_metadata)

    def parse_response(self, response) -> Callable[[Literal["to_user", "tool_call"]], AsyncGenerator]:
        return self.tool_model.parse_response(response)
    
    def _validate_tool(self, tool: Callable) -> bool:
        if getattr(tool, "__tool__", None) is not True:
            raise ToolError(f"The '{tool}' is not a defined tool.")
        return True
