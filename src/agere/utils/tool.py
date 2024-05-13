import re
import inspect
from collections.abc import Callable
from typing import (
    Literal,
    Any,
    AsyncGenerator,
    AsyncIterator,
    Callable,
    TypeVar,
    overload,
)

from ._tool_base import (
    CustomToolModelInterface,
    ProvidedToolModelInterface,
    ToolKit,
    ToolsManagerInterface,
    ToolModelInterface,
    ToolMetadata,
)
from ._exceptions import AgereUtilsError


class ToolError(AgereUtilsError):
    """Raised when encountering an error related to the tool."""


F = TypeVar('F', bound=Callable[..., Any])

# Bare decorator usage.
@overload
def tool(__func: F) -> F: ...

# Decorator with arguments.
@overload
def tool(*, description: str = '') -> Callable[[F], F]: ...

# Implementation.
def tool(__func: Callable[..., Any] | None = None, *, description: str = ''):
    """Decorator for a tool."""

    from_docstring = True if __func is not None else False

    def decorator(func):
        func.__tool__ = True
        func.__tool_description__ = description
        if not hasattr(func, "__tool_parameters__"):
            func.__tool_parameters__ = []
        if not hasattr(func, "__tool_kit__"):
            func.__tool_kit__ = None
        
        if from_docstring:
            metadata = _parse_docstring(func)
            
            description_from_docstring = metadata["description"]
            if not func.__tool_description__:
                func.__tool_description__ = description_from_docstring

            param_from_docstring = metadata["parameters"]
            param_name_list = [param["name"] for param in func.__tool_parameters__]
            for param_docs in param_from_docstring:
                if param_docs["name"] not in param_name_list:
                    func.__tool_parameters__.append(param_docs)

        return func
    
    if __func is not None:
        return decorator(__func)
    else:
        return decorator

def tool_kit(tool_kit_name: str, tool_kit_description: str | None = None):
    """Decorator for a tool.
    
    Add the tool into a tool kit.
    """
    
    def decorator(func):
        global_name_space = globals()
        if tool_kit_name not in global_name_space:
            global_name_space[tool_kit_name] = ToolKit()
        tool_kit = global_name_space[tool_kit_name]
        func.__tool_kit__ = tool_kit

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

        matching_param = next(
            (
                param_info
                for param_info in func.__tool_parameters__
                if param_info.get("name") == name
            ),
            None,
        )

        if not matching_param:
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
        else:
            matching_param = {
                "name": name,
                "description": description,
                "default_value": default_value,
                "param_type": param_type,
                "choices": choices,
                "required": required,
            }

        return func

    return decorator

def _parse_docstring(func) -> dict:
    docstring = inspect.getdoc(func) or ''
    
    metadata = {
        'description': '',
        'parameters': []
    }
    
    param_pattern = re.compile(r'Args:\n\s*(.*?)(?=\n\nReturns:|$)', re.DOTALL)
    
    param_info_pattern = re.compile(r'(\w+)\s*(?:\(([^)]*)\))?\s*:(.*?)(?=\n|$)', re.DOTALL)
    
    description_pattern = re.compile(r'(.+?)(?=\n\nArgs:)', re.DOTALL)
    description_match = description_pattern.search(docstring)
    metadata['description'] = description_match.group(1).strip() if description_match else ''
    
    param_block_match = param_pattern.search(docstring)
    if param_block_match:
        param_block = param_block_match.group(1)
        
        for param_match in param_info_pattern.finditer(param_block):
            param_name = param_match.group(1)
            param_type = param_match.group(2).strip() if param_match.group(2) else 'string'
            param_description = param_match.group(3).strip()
            
            metadata['parameters'].append(
                {
                    'name': param_name,
                    'description': param_description,
                    'default_value': '',
                    'param_type': param_type,
                    'choices': None,
                    'required': True,
                }
            )
    
    return metadata


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

    def add_tool(self, tool: Callable | ToolKit, tool_type: Literal["PERMANENT", "TEMPORARY"] = "TEMPORARY") -> None:
        self._validate_tool(tool)
        if isinstance(tool, ToolKit):
            tools = tool.tools
        else:
            tools = [tool]
        for one_tool in tools:
            if tool_type == "PERMANENT":
                self._permanent_tools[one_tool.__name__] = self.create_tool_metadata(one_tool)
            if tool_type == "TEMPORARY":
                self._temporary_tools[one_tool.__name__] = self.create_tool_metadata(one_tool)
    
    def add_tools(
        self,
        tools: list[Callable | ToolKit],
        tool_type: Literal["PERMANENT", "TEMPORARY"] = "TEMPORARY",
    ) -> None:
        for tool in tools:
            self.add_tool(tool, tool_type=tool_type)
    
    def remove_tool(
        self,
        tool: Callable | str | ToolKit,
        tool_type: Literal["PERMANENT", "TEMPORARY"] = "TEMPORARY",
    ) -> None:
        if isinstance(tool, str):
            if tool_type == "PERMANENT":
                self._permanent_tools.pop(tool, None)
            if tool_type == "TEMPORARY":
                self._temporary_tools.pop(tool, None)
            return
        self._validate_tool(tool)
        if isinstance(tool, ToolKit):
            tools = tool.tools
        else:
            tools = [tool]
        for one_tool in tools:
            if tool_type == "PERMANENT":
                self._permanent_tools.pop(one_tool.__name__, None)
            if tool_type == "TEMPORARY":
                self._temporary_tools.pop(one_tool.__name__, None)
    
    def remove_tools(
        self,
        tools: list[Callable | str | ToolKit],
        tool_type: Literal["PERMANENT", "TEMPORARY"] = "TEMPORARY",
    ) -> None:
        for tool in tools:
            self.remove_tool(tool, tool_type=tool_type)
    
    def clear_tools(self, tool_type: Literal["PERMANENT", "TEMPORARY"] = "TEMPORARY") -> None:
        if tool_type == "PERMANENT":
            self._permanent_tools = {}
        if tool_type == "TEMPORARY":
            self._temporary_tools = {}
    
    def register_tool(self, tool: Callable | ToolKit) -> None:
        self._validate_tool(tool)
        if isinstance(tool, ToolKit):
            tools = tool.tools
        else:
            tools = [tool]
        for one_tool in tools:
            self._registered_tools[one_tool.__name__] = self.create_tool_metadata(one_tool)
    
    def register_tools(self, tools: list[Callable | ToolKit]) -> None:
        for tool in tools:
            self.register_tool(tool)
    
    def unregister_tools(self, tools: list[Callable | str | ToolKit]) -> None:
        for tool in tools:
            if isinstance(tool, str):
                self._registered_tools.pop(tool, None)
                return
            self._validate_tool(tool)
            if isinstance(tool, ToolKit):
                tools_list = tool.tools
            else:
                tools_list = [tool]
            for one_tool in tools_list:
                self._registered_tools.pop(one_tool.__name__, None)

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
            tool_kit = tool.__tool_kit__,
        )
        return tool_metadata
    
    def get_tools_metadata(
        self,
        by_types: list[Literal["PERMANENT", "TEMPORARY"]] | Literal["ALL"] = "ALL",
        by_names: list[str | ToolKit] | None = None,
    ) -> list[ToolMetadata]:
        tool_names = set()
        by_types = ["PERMANENT", "TEMPORARY"] if by_types == "ALL" else by_types
        if "PERMANENT" in by_types:
            tool_names.update(self._permanent_tools.keys())
        if "TEMPORARY" in by_types:
            tool_names.update(self._temporary_tools.keys())
        if by_names:
            tool_names.update(by_names)
        return self.get_tools_metadata_by_names(list(tool_names))

    def get_tools_metadata_by_names(self, names: list[str | ToolKit]) -> list[ToolMetadata]:
        result = []
        for name in names:
            if isinstance(name, ToolKit):
                tools = name.tools
                names_list = [tool.name for tool in tools]
            else:
                names_list = [name]
            for one_name in names_list:
                if one_name in self._registered_tools:
                    result.append(self._registered_tools[one_name])
                    continue
                if one_name in self._temporary_tools:
                    result.append(self._temporary_tools[one_name])
                    continue
                if one_name in self._permanent_tools:
                    result.append(self._permanent_tools[one_name])
                    continue
        return result

    def get_tools_manual(
        self,
        by_types: list[Literal["PERMANENT", "TEMPORARY"]] | Literal["ALL"] = "ALL",
        by_names: list[str | ToolKit] | None = None,
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

    def wrap_tools_to_bead(self, tools: list[ToolMetadata | Callable | ToolKit]) -> list:
        assert isinstance(self.tool_model, CustomToolModelInterface), (
            "The method 'wrap_tools_to_bead' should only be used when utilizing "
            "a CustomToolModelInterface type of tool model."
        )
        tools_metadata_list = []
        for tool in tools:
            if isinstance(tool, ToolMetadata):
                tools_metadata_list.append(tool)
            if isinstance(tool, ToolKit):
                for one_tool in tool.tools:
                    tools_metadata_list.append(self.create_tool_metadata(one_tool))
            if isinstance(tool, Callable):
                tools_metadata_list.append(self.create_tool_metadata(tool))
            else:
                assert False
        description = self.tool_model.get_tools_manual(tools_metadata_list)
        tool_bead = self.tool_model.tool_manual_bead_maker(description)
        return [tool_bead]

    def tools_manual_token_num(
        self,
        by_types: list[Literal["PERMANENT", "TEMPORARY"]] | Literal["ALL"] = "ALL",
        by_names: list[str | ToolKit] | None = None,
    ) -> int:
        assert isinstance(self.tool_model, ProvidedToolModelInterface), (
            "The method 'tools_manual_token_num' should only be used when utilizing "
            "a ProvidedToolModelInterface type of tool model."
        )
        tools_metadata = self.get_tools_metadata(by_types=by_types, by_names=by_names)
        return self.tool_model.tool_manual_token_counter(tools_metadata)

    def parse_response(
        self,
        response: AsyncIterator
    ) -> Callable[[Literal["to_user", "tool_call"]], AsyncGenerator]:
        return self.tool_model.parse_response(response)
    
    def _validate_tool(self, tool: Callable | ToolKit) -> bool:
        if getattr(tool, "__tool__", None) is True:
            return True
        if isinstance(tool, ToolKit):
            return True
        raise ToolError(f"The '{tool}' is not a defined tool.")
