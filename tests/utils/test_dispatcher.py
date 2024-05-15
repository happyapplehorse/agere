import json

from agere.utils.dispatcher import async_dispatcher_tools_call_for_openai


async def test_dispatcher(async_openai_response_fixture):
    # Setup
    async_iterable = async_openai_response_fixture

    # Action
    make_role_generator = await async_dispatcher_tools_call_for_openai(source=async_iterable)
    to_user_gen = make_role_generator("to_user")
    function_call_gen = make_role_generator("tool_call")
    to_user_list = []
    function_call_list = []
    async for to_user in to_user_gen:
        to_user_list.append(to_user)
    async for function_call in function_call_gen:
        function_call_list.append(function_call)

    # Assert
    assert ''.join(to_user_list) == ''.join(['I am search \\"weather\\" for you.', '\n', 'I am search weather in Beijing.'])
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
