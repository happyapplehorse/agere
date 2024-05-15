import pytest
from dataclasses import dataclass
from typing import AsyncIterable


@dataclass
class ChoiceDeltaToolCallFunction:
    arguments: str | None = None
    name: str | None = None

@dataclass
class ChoiceDeltaToolCall:
    index: int = 0
    id: str | None = None
    function: ChoiceDeltaToolCallFunction | None = None
    type: str | None = None
    

@dataclass
class ChoiceDelta:
    content: str | None = None
    function_call: list | None = None
    role: str | None = None
    tool_calls: list[ChoiceDeltaToolCall] | None = None


@dataclass
class Choice:
    delta: ChoiceDelta | None = None
    choices: list | None = None
    finish_reason: str | None = None
    index: int = 0

@dataclass
class ChatCompletionChunk:
    id: str | None = None
    choices: list | None = None

response = [
    # Chunk No.1
    ChatCompletionChunk(
        id='chatcmpl-8Rz2q1FonSqzWAexwcszkWHyQoMgH',
        choices=[
            Choice(
                delta=ChoiceDelta(
                    content=None,
                    function_call=None,
                    role='assistant',
                    tool_calls=None
                ),
                finish_reason=None,
                index=0
            )
        ],
    ),
    # Chunk No.2
    ChatCompletionChunk(
        id='chatcmpl-8Rz2q1FonSqzWAexwcszkWHyQoMgH',
        choices=[
            Choice(
                delta=ChoiceDelta(
                    content=None,
                    function_call=None,
                    role=None,
                    tool_calls=[
                        ChoiceDeltaToolCall(
                            index=0,
                            id='call_vM7ZCfu7VF0curI2YwIpCNVh',
                            function=ChoiceDeltaToolCallFunction(
                                arguments='',
                                name='get_current_weather'
                            ),
                            type='function'
                        )
                    ]
                ),
                finish_reason=None,
                index=0
            )
        ], 
    ),
    # Chunk No.3
    ChatCompletionChunk(
        id='chatcmpl-8Rz2q1FonSqzWAexwcszkWHyQoMgH',
        choices=[
            Choice(
                delta=ChoiceDelta(
                    content=None,
                    function_call=None,
                    role=None,
                    tool_calls=[
                        ChoiceDeltaToolCall(
                            index=0,
                            id=None,
                            function=ChoiceDeltaToolCallFunction(
                                arguments='{"to',
                                name=None
                            ),
                            type=None
                        )
                    ]
                ),
                finish_reason=None,
                index=0
            )
        ],
    ),
    # Chunk No.4
    ChatCompletionChunk(
        id='chatcmpl-8Rz2q1FonSqzWAexwcszkWHyQoMgH',
        choices=[
            Choice(
                delta=ChoiceDelta(
                    content=None,
                    function_call=None,
                    role=None,
                    tool_calls=[
                        ChoiceDeltaToolCall(
                            index=0,
                            id=None,
                            function=ChoiceDeltaToolCallFunction(
                                arguments='_user',
                                name=None
                            ),
                            type=None
                        )
                    ]
                ),
                finish_reason=None,
                index=0
            )
        ],
    ),
    # Chunk No.5 to the second-to-last chunk before the tools call ends.
    ChatCompletionChunk(
        id='chatcmpl-8Rz2q1FonSqzWAexwcszkWHyQoMgH',
        choices=[
            Choice(
                delta=ChoiceDelta(
                    content=None,
                    function_call=None,
                    role=None,
                    tool_calls=[
                        ChoiceDeltaToolCall(
                            index=0,
                            id=None,
                            function=ChoiceDeltaToolCallFunction(
                                arguments='": "I am search \\"weather\\" for you.", "location": "Par',
                                name=None
                            ),
                            type=None
                        )
                    ]
                ),
                finish_reason=None,
                index=0
            )
        ],
    ),
    # The last chunk in first tools call.
    ChatCompletionChunk(
        id='chatcmpl-8Rz2q1FonSqzWAexwcszkWHyQoMgH',
        choices=[
            Choice(
                delta=ChoiceDelta(
                    content=None,
                    function_call=None,
                    role=None,
                    tool_calls=[
                        ChoiceDeltaToolCall(
                            index=0,
                            id=None,
                            function=ChoiceDeltaToolCallFunction(
                                arguments='is"}',
                                name=None
                            ),
                            type=None
                        )
                    ]
                ),
                finish_reason=None,
                index=0
            )
        ],
    ),
    # Chunk No.1 to call the second tool.
    ChatCompletionChunk(
        id='chatcmpl-8Rz2q1FonSqzWAexwcszkWHyQoMgH',
        choices=[
            Choice(
                delta=ChoiceDelta(
                    content=None,
                    function_call=None,
                    role=None,
                    tool_calls=[
                        ChoiceDeltaToolCall(
                            index=1,
                            id='call_AOefM0a9RMWTiJmOSDsW2mZM',
                            function=ChoiceDeltaToolCallFunction(
                                arguments='',
                                name='get_current_weather'
                            ),
                            type='function'
                        )
                    ]
                ),
                finish_reason=None,
                index=0
            )
        ],
    ),
    # Chunk No.2- to call the second tool.
    ChatCompletionChunk(
        id='chatcmpl-8Rz2q1FonSqzWAexwcszkWHyQoMgH',
        choices=[
            Choice(
                delta=ChoiceDelta(
                    content=None,
                    function_call=None,
                    role=None,
                    tool_calls=[
                        ChoiceDeltaToolCall(
                            index=1,
                            id=None,
                            function=ChoiceDeltaToolCallFunction(
                                arguments='{"to_user": "I am search weather in Beijing.", "location": "Beijing", "unit": "celsiu',
                                name=None
                            ),
                            type=None
                        )
                    ]
                ),
                finish_reason=None,
                index=0
            )
        ],
    ),
    # Last chunk in tool_calls.
    ChatCompletionChunk(
        id='chatcmpl-8Rz2q1FonSqzWAexwcszkWHyQoMgH',
        choices=[
            Choice(
                delta=ChoiceDelta(
                    content=None,
                    function_call=None,
                    role=None,
                    tool_calls=[
                        ChoiceDeltaToolCall(
                            index=1,
                            id=None,
                            function=ChoiceDeltaToolCallFunction(
                                arguments='s"}',
                                name=None
                            ),
                            type=None
                        )
                    ]
                ),
                finish_reason=None,
                index=0
            )
        ],
    ),
    # Last chunk of all.
    ChatCompletionChunk(
        id='chatcmpl-8Rz2q1FonSqzWAexwcszkWHyQoMgH',
        choices=[
            Choice(
                delta=ChoiceDelta(
                    content=None,
                    function_call=None,
                    role=None,
                    tool_calls=None
                ),
                finish_reason='tool_calls',
                index=0
            )
        ],
    ),
]


@pytest.fixture
def async_openai_response() -> AsyncIterable:
            
    async def async_gen(iterable):
        for item in iterable:
            yield item
    
    return async_gen(response)
