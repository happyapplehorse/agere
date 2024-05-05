import logging
from collections.abc import Callable
from typing import AsyncGenerator, AsyncIterator, Literal

from .._tool_base import ToolModelInterface, ToolMetadata
from ..dispatcher import async_dispatcher_tools_call_for_openai


class OpenaiToolModel(ToolModelInterface):

    def __init__(
        self,
        tool_token_counter: Callable[[str], int],
        to_user_flag: str | None = "to_user",
        logger: logging.Logger | None = None,
    ):
        self.tool_token_counter = tool_token_counter
        if to_user_flag is None:
            to_user_flag = "__THIS_IS_A_NEVER_USED_NAME__"
        self.to_user_flag = to_user_flag
        self.logger = logger

    @property
    def tool_model_name(self) -> str:
        return "OPENAI"

    def tool_manual_token_counter(self, tools: list[ToolMetadata]) -> int:
        manual = str(self.get_tools_manual(tools=tools))
        return self.tool_token_counter(manual)

    def get_tools_manual(self, tools: list[ToolMetadata]) -> list[dict]:
        manual = []
        for tool in tools:
            manual.append(
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": {
                            "type": "object",
                            "properties:": (parameters := {}),
                            "required": (required := []),
                        },
                    },
                },
            )
            if self.to_user_flag:
                parameters[self.to_user_flag] = {
                    "type": "string",
                    "description": (
                        "The content paraphrased for the user. "
                        "The content of this parameter can tell the user what you are about to do, "
                        "or it can be an explanation of the behavior of the function calling. "
                        "For example, 'I'm going to search the internet, please wait a moment.'"
                    ),
                }
            for param in tool.parameters:
                parameters[param["name"]] = {
                    "type": "string",
                    "description": param["description"],
                }
                if param["choices"]:
                    parameters[param["name"]]["enum"] = param["choices"]
                if param["required"]:
                    required.append(param["name"])
        return manual
    
    async def parse_response(
        self,
        source: AsyncIterator,
    ) -> Callable[[Literal["to_user", "tool_call"]], AsyncGenerator]:
        gen_maker = await async_dispatcher_tools_call_for_openai(
            source=source,
            to_user_flag=self.to_user_flag,
            logger=self.logger,
        )        
        return gen_maker
