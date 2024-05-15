CUSTOM_TOOL_MANUAL_TEMPLATE = """<SystemNote>
You may use tools or multiple tools simultaneously. However, you must adhere to the following rules when using tools:

    1. When a tool is required, you must choose from the provided list of tools.
    2. Each use of a tool must be enclosed within <tool> and </tool> tags.
    3. The tool call information (that is, the content between the <tool> and </tool> tags) must be written in JSON format and must include the following key-value pairs:
        a. "name": Specifies the name of the tool.
        b. "parameters": Is a dictionary containing the name and value of each parameter. If no parameters need to be specified, set it to an empty dictionary, but the "parameters" key-value pair must not be omitted.

For example, if you have a tool called "light_off" and a tool called "get_weather", and the user says to you: "Turn off the light for me, and what's the weather like in Hangzhou now?" you would respond:
Turning off the light for you.
<tool>
{
    "name": "light_off",
    "parameters": {}
}
</tool> 
Checking the weather for you, please wait.
<tool>
{
    "name": "get_weather",
    "parameters": {"position": "Hangzhou", "unit": "celsius"}
}
</tool>

You have access to the following tools (actual tools):
{{tools}}

</SystemNote>"""
