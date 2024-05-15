import re
import inspect
from collections.abc import Callable, Coroutine
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
    """Decorator for a tool.

    It can be used with or without arguments. When used with arguments,
    the description of the tool can be manually specified.
    When used without arguments, the tool's metadata will automatically
    be extracted from the docstring of the decorated function,
    including the tool's description, and the name, type, and corresponding
    description of each parameter of the tool.
    Additionally, the tool_parameter decorator can be used to set more or
    more specific metadata for a particular parameter,
    which will override all metadata for that parameter.
    """

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
            param_name_list = [param_info["name"] for param_info in func.__tool_parameters__]
            for param_docs in param_from_docstring:
                if param_docs["name"] not in param_name_list:
                    func.__tool_parameters__.append(param_docs)

        return func
    
    if __func is not None:
        return decorator(__func)
    else:
        return decorator

def tool_kit(kit: str | ToolKit, description: str | None = None):
    """Decorator for a tool.

    This decorator is used to add a tool into a tool kit.
    It also allows setting a description for the tool kit.
    
    Args:
        kit (str | ToolKit): The name of the tool kit or the ToolKit object to add the tool into.
        description (str | None, optional):
            A description for the tool kit.
            When it is not None, it will overwrite the tool kit description.
            When it is None, it will retain the original tool kit description,
            if it exists.
    """
    
    def decorator(func):
        if isinstance(kit, ToolKit):
            the_kit = kit
        elif isinstance(kit, str):
            global_name_space = globals()
            if kit not in global_name_space:
                global_name_space[kit] = ToolKit(kit)
            the_kit = global_name_space[kit]
        else:
            assert False
        
        func.__tool_kit__ = the_kit

        if description is not None:
            the_kit.description = description
        the_kit.tools.append(func)
        
        return func
    
    return decorator

def tool_parameter(
    *,
    name: str,
    description: str,
    default_value: Any = "",
    param_type: str = "string",
    choices: list | None = None,
    required: bool = True,
):
    """Decorator for tool parameters.

    It will set the full infomation of the specified parameter.

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
    """Parses a function's docstring to extract metadata.
    
    This internal function is used by the 'tool' decorator to parse the docstring
    and extract the tool's description and parameters.
    
    Args:
        func (Callable): The function whose docstring is to be parsed.
    
    Returns:
        dict: A dictionary containing the description and parameters extracted
        from the docstring.
    """
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
    """A class that manages tools.

    Allowing for tool registration, addition, removal, and querying,
    as well as the generation of tool metadata and manuals.
    """
    def __init__(self, tool_model: ToolModelInterface):
        self._tool_model = tool_model
        self._permanent_tools: dict[str, ToolMetadata] = {}
        self._temporary_tools: dict[str, ToolMetadata] = {}
        self._registered_tools: dict[str, ToolMetadata] = {}
    
    @property
    def tool_model_name(self) -> str:
        """Get the name of the tool model."""
        return self.tool_model.tool_model_name
    
    @property
    def tool_model_type(self) -> Literal["CUSTOM", "PROVIDED"]:
        """Get the type of the tool model.
        
        Returns:
            Either 'CUSTOM' or 'PROVIDED'.
            'CUSTOM' means that LLM does not provide an excuse for tool invocation,
            and a custom protocol is used to implement tool invocation.
            'PROVIDED' means using the tool invocation interface provided by LLM itself.
        """
        if isinstance(self._tool_model, CustomToolModelInterface):
            return "CUSTOM"
        elif isinstance(self._tool_model, ProvidedToolModelInterface):
            return "PROVIDED"
        else:
            assert False

    @property
    def tool_model(self) -> ToolModelInterface:
        """Get the tool model instance."""
        return self._tool_model

    @tool_model.setter
    def tool_model(self, value: ToolModelInterface):
        """Set the tool model instance."""
        self._tool_model = value

    def add_tool(
        self,
        tool: Callable | ToolKit,
        tool_type: Literal["PERMANENT", "TEMPORARY"] = "TEMPORARY",
    ) -> None:
        """Add a single tool to the tool manager.

        Args:
            tool (Callable | ToolKit): The tool or tool kit to add.
            tool_type (Literal["PERMANENT", "TEMPORARY"], optional):
                The type of tool to add, either "PERMANENT" or "TEMPORARY".
                Defaults to "TEMPORARY".

        Raises:
            ToolError: If the provided tool is not a defined tool.
        """
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
        """Add multiple tools to the tool manager.

        Args:
            tools (list[Callable | ToolKit]): A list of tools or tool kits to add.
            tool_type (Literal["PERMANENT", "TEMPORARY"], optional):
                The type of tools to add, either "PERMANENT" or "TEMPORARY".
                Defaults to "TEMPORARY".

        Raises:
            ToolError: If any of the provided tools is not a defined tool.
        """
        for tool in tools:
            self.add_tool(tool, tool_type=tool_type)
    
    def remove_tool(
        self,
        tool: Callable | str | ToolKit,
        tool_type: Literal["PERMANENT", "TEMPORARY"] = "TEMPORARY",
    ) -> None:
        """Remove a single tool from the tool manager.
        
        If the tool to be removed cannot be found, do nothing and will not raise an error.

        Args:
            tool (Callable | str | ToolKit):
                The tool, tool kit, or name of the tool to remove.
            tool_type (Literal["PERMANENT", "TEMPORARY"], optional):
                The type of tool to remove from, either "PERMANENT" or "TEMPORARY".
                Defaults to "TEMPORARY".
        """
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
        """Remove multiple tools from the tool manager.
        
        If the tool to be removed cannot be found, do nothing and will not raise an error.
        
        Args:
            tools (list[Callable | str | ToolKit]):
                A list of tools, tool kits, or names of tools to remove.
            tool_type (Literal["PERMANENT", "TEMPORARY"], optional):
                The type of tools to remove from, either "PERMANENT" or "TEMPORARY".
                Defaults to "TEMPORARY".
        """
        for tool in tools:
            self.remove_tool(tool, tool_type=tool_type)
    
    def clear_tools(self, tool_type: Literal["PERMANENT", "TEMPORARY"] = "TEMPORARY") -> None:
        """Clear all tools of a specified type from the tool manager.

        Args:
            tool_type (Literal["PERMANENT", "TEMPORARY"], optional):
                The type of tools to clear, either "PERMANENT" or "TEMPORARY".
                Defaults to "TEMPORARY".
        """
        if tool_type == "PERMANENT":
            self._permanent_tools = {}
        if tool_type == "TEMPORARY":
            self._temporary_tools = {}
    
    def register_tool(self, tool: Callable | ToolKit) -> None:
        """Register a single tool with registered tool list of the tool manager.

        Args:
            tool (Callable | ToolKit): The tool or tool kit to register.

        Raises:
            ToolError: If the provided tool is not a defined tool.
        """
        self._validate_tool(tool)
        if isinstance(tool, ToolKit):
            tools = tool.tools
        else:
            tools = [tool]
        for one_tool in tools:
            self._registered_tools[one_tool.__name__] = self.create_tool_metadata(one_tool)
    
    def register_tools(self, tools: list[Callable | ToolKit]) -> None:
        """Register multiple tools with the registered tool list of the tool manager.

        Args:
            tools (list[Callable | ToolKit]):
                A list of tools or tool kits to register.

        Raises:
            ToolError: If any of the provided tools is not a defined tool.
        """
        for tool in tools:
            self.register_tool(tool)
    
    def unregister_tools(self, tools: list[Callable | str | ToolKit]) -> None:
        """Unregister multiple tools from the registered tool list of the tool manager.

        Args:
            tools (list[Callable | str | ToolKit]):
                A list of tools, tool kits, or names of tools to unregister.
        """
        for tool in tools:
            if isinstance(tool, str):
                self._registered_tools.pop(tool, None)
                continue
            self._validate_tool(tool)
            if isinstance(tool, ToolKit):
                tools_list = tool.tools
            else:
                tools_list = [tool]
            for one_tool in tools_list:
                self._registered_tools.pop(one_tool.__name__, None)

    def clear_registered_tools(self) -> None:
        """Clear all registered tools from the registered tool list of the tool manager."""
        self._registered_tools = {}

    @property
    def registered_tool_names(self) -> list[str]:
        """Get the list of names of all registered tools.

        Returns:
            list[str]: The list of tool names in _registered_tools of the tool manager.
        """
        return list(self._registered_tools.keys())

    @property
    def all_tools_names(self) -> list[str]:
        """Geta the list of names of all tools, both permanent, temporary, and registered.

        Returns:
            list[str]: The list of all tool names.
        """
        result = set()
        result.update(self._permanent_tools.keys())
        result.update(self._temporary_tools.keys())
        result.update(self._registered_tools.keys())
        return list(result)

    def create_tool_metadata(self, tool: Callable) -> ToolMetadata:
        """Create metadata for a given tool.

        Args:
            tool (Callable): The tool for which to create metadata.

        Returns:
            ToolMetadata: The metadata for the tool.

        Raises:
            ToolError: If the provided tool is not a defined tool.
        """
        self._validate_tool(tool)
        tool_metadata = ToolMetadata(
            name = tool.__name__,
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
        """Get metadata for tools based on type and/or name.

        Args:
            by_types (list[Literal["PERMANENT", "TEMPORARY"]] | Literal["ALL"], optional):
                The types of tools to get metadata for. Defaults to "ALL".
            by_names (list[str | ToolKit] | None, optional):
                The specific names or tool kits to get metadata for. Defaults to None.

        Returns:
            list[ToolMetadata]: The list of tool metadata.
        """
        tool_names = []
        by_types = ["PERMANENT", "TEMPORARY"] if by_types == "ALL" else by_types
        if "PERMANENT" in by_types:
            tool_names.extend([name for name in self._permanent_tools.keys() if name not in tool_names])
        if "TEMPORARY" in by_types:
            tool_names.extend([name for name in self._temporary_tools.keys() if name not in tool_names])
        if by_names:
            tool_names.extend([name for name in by_names if name not in tool_names])
        return self.get_tools_metadata_by_names(tool_names)

    def get_tools_metadata_by_names(self, names: list[str | ToolKit]) -> list[ToolMetadata]:
        """Get metadata for tools based on a list of names or tool kits.

        Args:
            names (list[str | ToolKit]): The list of tool names or tool kits to get metadata for.

        Returns:
            list[ToolMetadata]: The list of tool metadata.
        """
        result = []
        for name in names:
            if isinstance(name, ToolKit):
                tools = name.tools
                names_list = [tool.__name__ for tool in tools]
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
        """Get the manual for tools based on type and/or name.

        Args:
            by_types (list[Literal["PERMANENT", "TEMPORARY"]] | Literal["ALL"], optional):
                The types of tools to get the manual for. Defaults to "ALL".
            by_names (list[str | ToolKit] | None, optional):
                The specific names or tool kits to get the manual for. Defaults to None.

        Returns:
            Any: The manual for the tools.
        """
        tools = self.get_tools_metadata(by_types=by_types, by_names=by_names)
        return self.tool_model.get_tools_manual(tools=tools)

    def get_linked_tool(self, tool_name: str) -> Callable:
        """Get the callable linked tool by its name.

        Args:
            tool_name (str): The name of the tool.

        Returns:
            Callable: The linked tool.

        Raises:
            ValueError: If there is no corresponding tool for the given name.
        """
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
        """Wrap tools into a bead format as required by the tool model.

        Args:
            tools (list[ToolMetadata | Callable | ToolKit]):
                The list of tools (ToolMetadata or Callable tool) or tool kits.

        Returns:
            list: The wrapped tools infomation in bead format.
        """
        assert isinstance(self.tool_model, CustomToolModelInterface), (
            "The method 'wrap_tools_to_bead' should only be used when utilizing "
            "a CustomToolModelInterface type of tool model."
        )
        tools_metadata_list = []
        for tool in tools:
            if isinstance(tool, ToolMetadata):
                tools_metadata_list.append(tool)
            elif isinstance(tool, ToolKit):
                for one_tool in tool.tools:
                    tools_metadata_list.append(self.create_tool_metadata(one_tool))
            elif isinstance(tool, Callable):
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
        """Get the number of tokens in the manual for tools based on type and/or name.

        Args:
            by_types (list[Literal["PERMANENT", "TEMPORARY"]] | Literal["ALL"], optional):
                The types of tools to count tokens for. Defaults to "ALL".
            by_names (list[str | ToolKit] | None, optional):
                The specific names or tool kits to count tokens for. Defaults to None.

        Returns:
            int: The number of tokens in the manual.
        """
        assert isinstance(self.tool_model, ProvidedToolModelInterface), (
            "The method 'tools_manual_token_num' should only be used when utilizing "
            "a ProvidedToolModelInterface type of tool model."
        )
        tools_metadata = self.get_tools_metadata(by_types=by_types, by_names=by_names)
        return self.tool_model.tool_manual_token_counter(tools_metadata)

    def parse_response(
        self,
        response: AsyncIterator
    ) -> Coroutine[Any, Any, Callable[[Literal["to_user", "tool_call"]], AsyncGenerator]]:
        """Parse the response from the LLM.

        It will return a factory function, with which you can respectively obtain an
        asynchronous generator for the messages sent to the user and an asynchronous
        generator for function calls.

        Args:
            response (AsyncIterator): The response to parse.

        Returns:
            Callable: The factory function to make asynchronous generator.
        """
        return self.tool_model.parse_response(response)
    
    def _validate_tool(self, tool: Callable | ToolKit) -> bool:
        """Validate whether the provided object is a tool or tool kit."""
        if getattr(tool, "__tool__", None) is True:
            return True
        if isinstance(tool, ToolKit):
            return True
        raise ToolError(f"The '{tool}' is not a defined tool.")
