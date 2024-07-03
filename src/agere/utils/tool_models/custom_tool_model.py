import asyncio
import json
from collections.abc import Callable, Coroutine
from typing import Any, AsyncIterator, AsyncGenerator, Literal

from .custom_tool_prompt import CUSTOM_TOOL_MANUAL_TEMPLATE
from .._tool_base import CustomToolModelInterface, ToolMetadata, ParseResponseError
from ..prompt_template import render_prompt


class CustomToolModel(CustomToolModelInterface):
    """CustomToolModel is a class that implements the CustomToolModelInterface.

    Attributes:
        tool_bead_maker (Callable[[str], Any]): A callable that takes a string and returns any type,
            used to create tool beads from a manual.
        custom_tool_manual_template (str | None): Optional custom template for the tool manual.
            If None, a default template is used.

    Methods:
        tool_model_name: Property to get the name of the tool model.
        custom_tool_manual_template: Property to get or set the custom tool manual template.
        tool_manual_bead_maker: Method to create a tool manual bead from a manual string.
        get_tools_manual: Method to generate a tools manual from a list of ToolMetadata.
        parse_response: Asynchronous method to parse responses from LLM.
    """

    def __init__(
        self,
        tool_bead_maker: Callable[[str], Any],
        custom_tool_manual_template: str | None = None,
    ):
        """
        Initializes a new instance of the CustomToolModel class with a tool bead maker callable
        and an optional custom tool manual template.

        Args:
            tool_bead_maker (Callable[[str], Any]):
                The callable used to create tool beads. It takes a string as input and
                return the bead created from it.
            custom_tool_manual_template (str | None, optional): The custom template for the tool manual.
        """
        self.tool_bead_maker: Callable[[str], Any] = tool_bead_maker
        self._custom_tool_manual_template = custom_tool_manual_template

    @property
    def tool_model_name(self):
        """Gets the name of the tool model."""
        return "CUSTOM"

    @property
    def custom_tool_manual_template(self) -> str:
        """
        Gets the custom tool manual template.

        Returns:
            str: The custom tool manual template or a default template if none is set.
        """
        return self._custom_tool_manual_template or CUSTOM_TOOL_MANUAL_TEMPLATE

    @custom_tool_manual_template.setter
    def custom_tool_manual_template(self, value: str) -> None:
        """
        Sets the custom tool manual template.

        Args:
            value (str): The new custom tool manual template which has a 'tools' variable.
        """
        self._custom_tool_manual_template = value

    def tool_manual_bead_maker(self, manual: str) -> Any:
        """
        Creates a tool manual bead using the tool bead maker callable.

        Args:
            manual (str): The manual string used to create the tool manual bead.

        Returns:
            Any: The result of the tool bead maker callable.
        """
        return self.tool_bead_maker(manual)

    def get_tools_manual(self, tools: list[ToolMetadata]) -> Any:
        """
        Generates a tools manual from a list of ToolMetadata.

        Args:
            tools (list[ToolMetadata]): The list of tool metadata objects.

        Returns:
            Any: The generated tools manual.
        """
        tools_instruction = []
        for tool in tools:
            tool_dict = {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters,
            }
            tools_instruction.append(tool_dict)
        tools_instruction_str = json.dumps(tools_instruction, indent=4)
        return render_prompt(
            self.custom_tool_manual_template,
            tools=tools_instruction_str,
        )

    async def parse_response(
        self,
        source: AsyncIterator,
    ) -> Callable[[Literal["to_user", "tool_call"]], AsyncGenerator]:
        """
        Parses asynchronous responses from LLM.

        Args:
            source (AsyncIterator): The asynchronous iterator source for the responses.

        Returns:
            Callable[[Literal["to_user", "tool_call"]], AsyncGenerator]:
            A callable that generates an asynchronous generator for either "to_user"
            or "tool_call" content.
        """
        parser = self.ParseResponse(source)
        return await parser.parse()


    class ParseResponse:

        State = Literal["closed", "in_to_user", "check_tool_start", "in_tool"]

        def __init__(self, source: AsyncIterator):
            self.source = source
            self.state: CustomToolModel.ParseResponse.State = "closed"
            self.to_user_queue = asyncio.Queue()
            self.tool_queue = asyncio.Queue()
            self._check_tag_buffer = ""
            self._tool_call_buffer = ""

        async def run(self) -> None:
            async for chunk in self.source:
                await self.state_method(chunk)
            if self.state == "check_tool_start":
                await self.to_user_queue.put(self._check_tag_buffer)
                self._check_tag_buffer = ""
            await self.to_user_queue.put(None)
            await self.tool_queue.put(None)
            if self.state == "in_tool":
                raise ParseResponseError(f"The parser exits in state {self.state}.")
            self.state = "closed"

        async def parse(self):
            def make_generator(which: Literal["to_user", "tool_call"]):
                if which == "to_user":
                    queue = self.to_user_queue
                elif which == "tool_call":
                    queue = self.tool_queue
                else:
                    assert False
                async def generator():
                    while True:
                        value = await queue.get()
                        if value is None:
                            break
                        yield value
                return generator()
            asyncio.create_task(self.run())
            return make_generator

        @property
        def state_method(self) -> Callable[[str], Coroutine]:
            if self.state == "closed":
                return self._in_closed
            if self.state == "in_to_user":
                return self._in_to_user
            if self.state == "check_tool_start":
                return self._in_check_tool_start
            if self.state == "in_tool":
                return self._in_tool
            else:
                assert False

        async def _in_closed(self, chunk: str) -> None:
            assert self.state == "closed"
            self._check_tag_buffer = ""
            self._tool_call_buffer = ""
            self.state = "in_to_user"
            await self._in_to_user(chunk)
        
        async def _in_to_user(self, chunk: str) -> None:
            assert self.state == "in_to_user"
            tag_start = chunk.find("<")
            if tag_start == -1:
                await self.to_user_queue.put(chunk)
                self.state = "in_to_user"
                return
        
            await self.to_user_queue.put(chunk[:tag_start])
            self._check_tag_buffer = chunk[tag_start:]
            
            if len(self._check_tag_buffer) < 6:
                self.state = "check_tool_start"
                return

            if self._check_tag_buffer.startswith("<tool>"):
                self.state = "in_tool"
                self._tool_call_buffer = self._check_tag_buffer[6:]
                self._check_tag_buffer = ""
                await self._in_tool("")
                return
            
            await self.to_user_queue.put(self._check_tag_buffer)
            self._check_tag_buffer = ""
            self.state = "in_to_user"
            return
        
        async def _in_check_tool_start(self, chunk: str) -> None:
            assert self.state == "check_tool_start"
            self._check_tag_buffer += chunk
            
            if len(self._check_tag_buffer) < 6:
                self.state = "check_tool_start"
                return

            if self._check_tag_buffer.startswith("<tool>"):
                self.state = "in_tool"
                self._tool_call_buffer = self._check_tag_buffer[6:]
                self._check_tag_buffer = ""
                return
            
            await self.to_user_queue.put(self._check_tag_buffer)
            self._check_tag_buffer = ""
            self.state = "in_to_user"
            return
        
        async def _in_tool(self, chunk: str) -> None:
            assert self.state == "in_tool"
            self._tool_call_buffer += chunk

            tool_tag_end = self._tool_call_buffer.find("</tool>")
            if tool_tag_end == -1:
                self.state = "in_tool"
                return

            tool_call = self._tool_call_buffer[:tool_tag_end]
            await self.tool_queue.put(tool_call)
            self._tool_call_buffer = ""
            self.state = "in_to_user"
            await self._in_to_user(self._tool_call_buffer[tool_tag_end+7:])
            return
