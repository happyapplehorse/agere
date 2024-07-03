# Examples
The [requirements.txt](./requirements.txt) include all additional dependencies needed for all example programs.

## openai_chat_with_tools
This example demonstrates how to build a conversation flow with tool-calling capabilities using Agere.
To run this example, you need to set the environment variable `OPENAI_API_KEY` to your OpenAI API key.

### Dependencies
- openai>=1.2.3,<2


## openai_chat_with_tools_within_loop
This example has the same functionality as openai_chat_with_tools but demonstrates how to control the flow
via a callback feature. To run this example, you need to set the environment variable `OPENAI_API_KEY` to
your OpenAI API key.

### Dependencies
- openai>=1.2.3,<2


## openai_group_talk
This example builds a group chat agent where multiple AIs and the user participate together.
The chat participants speak in a multi-threaded preemptive manner instead of speaking through polling.
To run this example, you need to set the environment variable `OPENAI_API_KEY` to your OpenAI API key.
Note: To avoid excessive token consumption, please stop the group chat promptly by pressing `ctrl+c`.

### Dependencies
- openai>=1.2.3,<2
