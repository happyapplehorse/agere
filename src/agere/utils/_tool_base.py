from abc import ABCMeta, abstractmethod
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any, AsyncIterator, AsyncGenerator, Literal

from ._exceptions import AgereUtilsError


class ParseResponseError(AgereUtilsError):
    """Raised when parsing response encounters an error."""


class ToolKit:
    def __init__(
        self,
        name: str = '',
        description: str = '',
    ):
        self.name = name
        self.description = description
        self.tools: list[Callable] = []

    def __iter__(self):
        return iter(self.tools)

    def add_tools(self, tools: list[Callable]) -> None:
        self.tools.extend(tools)

    def set_description(self, description: str) -> None:
        self.description = description


@dataclass
class ToolMetadata:
    name: str
    description: str
    parameters: list[dict]
    linked_tool: Callable
    tool_kit: ToolKit | None


class ToolModelInterface(metaclass=ABCMeta):
    """Base class for ToolModel."""

    @property
    @abstractmethod
    def tool_model_name(self) -> str:
        ...

    @abstractmethod
    def get_tools_manual(self, tools: list[ToolMetadata]) -> Any:
        ...

    @abstractmethod
    async def parse_response(self, source: AsyncIterator) -> Callable[[Literal["to_user", "tool_call"]], AsyncGenerator]:
        ...


class CustomToolModelInterface(ToolModelInterface):
    """Base class for custom tool model."""

    @abstractmethod
    def tool_manual_bead_maker(self, manual: str) -> Any:
        ...


class ProvidedToolModelInterface(ToolModelInterface):
    """Base class for provided tool model."""

    @abstractmethod
    def tool_manual_token_counter(self, tools: list[ToolMetadata]) -> int:
        ...


class ToolsManagerInterface(metaclass=ABCMeta):
    """Base class for Tools."""
    
    @property
    @abstractmethod
    def tool_model_name(self) -> str:
        ...
    
    @property
    @abstractmethod
    def tool_model_type(self) -> Literal["CUSTOM", "PROVIDED"]:
        ...

    @property
    @abstractmethod
    def tool_model(self) -> ToolModelInterface:
        ...
    
    @tool_model.setter
    @abstractmethod
    def tool_model(self, value: ToolModelInterface):
        ...
    
    @abstractmethod
    def add_tool(self, tool: Callable | ToolKit, tool_type: Literal["PERMANENT", "TEMPORARY"] = "TEMPORARY") -> None:
        ...
    
    @abstractmethod
    def add_tools(self, tools: list[Callable | ToolKit], tool_type: Literal["PERMANENT", "TEMPORARY"] = "TEMPORARY") -> None:
        ...
    
    @abstractmethod
    def remove_tool(self, tool: Callable | str | ToolKit, tool_type: Literal["PERMANENT", "TEMPORARY"] = "TEMPORARY") -> None:
        ...
    
    @abstractmethod
    def remove_tools(self, tools: list[Callable | str | ToolKit], tool_type: Literal["PERMANENT", "TEMPORARY"] = "TEMPORARY") -> None:
        ...
    
    @abstractmethod
    def clear_tools(self, tool_type: Literal["PERMANENT", "TEMPORARY"] = "TEMPORARY") -> None:
        ...
    
    @abstractmethod
    def register_tool(self, tool: Callable | ToolKit) -> None:
        ...
    
    @abstractmethod
    def register_tools(self, tools: list[Callable | ToolKit]) -> None:
        ...
    
    @abstractmethod
    def unregister_tools(self, tools: list[Callable | str | ToolKit]) -> None:
        ...
    
    @abstractmethod
    def clear_registered_tools(self) -> None:
        ...
    
    @property
    @abstractmethod
    def registered_tool_names(self) -> list[str]:
        ...

    @property
    @abstractmethod
    def all_tools_names(self) -> list[str]:
        ...
    
    @abstractmethod
    def create_tool_metadata(self, tool: Callable) -> ToolMetadata:
        ...
    
    @abstractmethod
    def get_tools_metadata(
        self,
        by_types: list[Literal["PERMANENT", "TEMPORARY"]] | Literal["ALL"] = "ALL",
        by_names: list[str | ToolKit] | None = None,
    ) -> list[ToolMetadata]:
        ...
    
    @abstractmethod
    def get_tools_metadata_by_names(self, names: list[str | ToolKit]) -> list[ToolMetadata]:
        ...

    @abstractmethod
    def get_tools_manual(
        self,
        by_types: list[Literal["PERMANENT", "TEMPORARY"]] | Literal["ALL"] = "ALL",
        by_names: list[str | ToolKit] | None = None,
    ) -> Any:
        ...

    @abstractmethod
    def get_linked_tool(self, tool_name: str) -> Callable:
        ...

    @abstractmethod
    def wrap_tools_to_bead(self, tools: list[ToolMetadata | Callable | ToolKit]) -> list:
        ...

    @abstractmethod
    def tools_manual_token_num(
        self,
        by_types: list[Literal["PERMANENT", "TEMPORARY"]] | Literal["ALL"] = "ALL",
        by_names: list[str | ToolKit] | None = None,
    ) -> int:
        ...
    
    @abstractmethod
    def parse_response(self, response) -> Coroutine[Any, Any, Callable[[Literal["to_user", "tool_call"]], AsyncGenerator]]:
        ...
