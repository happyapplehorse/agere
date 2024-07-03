import pytest
from typing import AsyncIterable


response = [
    "Turning off ",
    "the light for you.",
    "<tool>",
    "{",
    '    "name": "light_off",',
    '    "param',
    'eters": {}',
    "}</t",
    "ool>", 
    "Checking the weather for you, please wait.",
    "<",
    "tool>",
    "{",
    '    "name": "get_weather",',
    '    "parameters": {"position": ',
    '"Hangzhou", "unit": "celsius"}',
    "}",
    "</tool",
    ">",
]


@pytest.fixture
def async_custom_llm_response() -> AsyncIterable:
    
    async def async_gen(iterable):
        for item in iterable:
            yield item

    return async_gen(response)
