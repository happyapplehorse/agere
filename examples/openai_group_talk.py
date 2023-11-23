import random
from typing import Iterable, AsyncIterable

from agere.commander import PASS_WORD, CommanderAsync, Job, handler, tasker
from agere.utils.llm_async_converters import LLMAsyncAdapter
from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam

# This srcipt assumes you have the OPENAI_API_KEY environment variable set to a valid OpenAI APK key.
"""Attention:
This script requires you to press Ctrl+C to stop running.
Please terminate the program promptly to avoid wasting tokens.
"""

class Role:
    def __init__(self, name: str, system_message: str):
        self.name = name
        self.context: list[ChatCompletionMessageParam] = [{"role": "system", "content": system_message}]
        self.openai_client = OpenAI()

    def chat(self, message_content: str, message_from: str):
        self.context.append({"role": "user", "name": message_from, "content": message_content})
        response = self.openai_client.chat.completions.create(
            messages=self.context,
            model="gpt-4",
            stream=True,
        )
        return response


class GroupTalkInit(Job):
    def __init__(self, init_chat: str):
        self.speaking = None
        self.init_chat = init_chat
        self.roles: dict[str, Role] = {}
        super().__init__()
    
    def create_role(self, role: Role, role_name: str):
        self.roles[role_name] = role
        
    @tasker(PASS_WORD)
    async def task(self):
        # you can put a job in jobs
        await self.put_job(TalkToAll(message_content=self.init_chat, message_from="HOST"))


class TalkToAll(Job):
    def __init__(self, message_content: str, message_from: str):
        self.message_content = message_content
        self.message_from = message_from
        super().__init__()

    @tasker(PASS_WORD)
    async def task(self):
        talk_manager = self.ancestor_chain[-2]
        assert isinstance(talk_manager, GroupTalkInit)
        response_dict = {}
        all_roles = list(talk_manager.roles.items())
        # Randomly shuffle the order to give each role an equal opportunity to speak.
        random.shuffle(all_roles)
        for role_name, role in all_roles:
            response_dict[role_name] = role.chat(message_content=f"{self.message_content}", message_from=self.message_from)
        talk_manager.speaking = None
        # you can return a handler, it will automatically be called
        return ResponseHandler().handle_response(response_dict=response_dict)


class ResponseHandler:
    @handler(PASS_WORD)
    async def handle_response(self, self_handler, response_dict: dict[str, Iterable]):
        items = list(response_dict.items())
        # Randomly shuffle the order to give each role an equal opportunity to speak.
        random.shuffle(items)
        for role_name, response in items:
            # you can call a handler in handlers
            self_handler.call_handler(self.parse_stream_response(role_name=role_name, stream_response=response))

    @handler(PASS_WORD)
    async def parse_stream_response(self, self_handler, role_name, stream_response):
        async_stream_response = LLMAsyncAdapter().llm_to_async_iterable(stream_response)
        talk_manager = self_handler.ancestor_chain[-2]
        assert isinstance(talk_manager, GroupTalkInit)
        full_response_content = await stream_response_print(role_name=role_name, async_stream_response=async_stream_response)
        if "Can I speak" in full_response_content:
            role = talk_manager.roles[role_name]
            if talk_manager.speaking:
                role.context.append({"role": "assistant", "content": "Can I speak?"})
                role.context.append({"role": "user", "name": "HOST", "content": f"SYS_INNER: HOST says to you: No, {talk_manager.speaking} is speaking."})
            else:
                role.context.append({"role": "assistant", "content": full_response_content})
                talk_manager.speaking = role_name
                response = role.chat(
                    message_content=f"SYS_INNER: HOST says to you: Yes, you are {role_name}, you can talk now.",
                    message_from="HOST",
                )
                async_talk_stream_response = LLMAsyncAdapter().llm_to_async_iterable(response)
                talk_content = await stream_response_print(role_name=role_name, async_stream_response=async_talk_stream_response)
                await self_handler.put_job(TalkToAll(message_content=talk_content, message_from=role_name))


async def stream_response_print(role_name: str, async_stream_response: AsyncIterable) -> str:
    chunk_list = []
    print()
    async for chunk in async_stream_response:
        chunk_choice = chunk.choices[0]
        chunk_content = chunk_choice.delta.content
        if not chunk_content:
            continue
        chunk_list.append(chunk_content)
        #print(chunk_content, end="", flush=True)
    full_response_content = ''.join(chunk_list)
    if not "Can I speak?" in full_response_content:
        print(f"{role_name} says: ".upper(), full_response_content)
    return full_response_content


if __name__ == "__main__":
    init_job = GroupTalkInit("Hello everyone, it's a beautiful day, please introduce yourselves.")
    
    def make_role_prompt(role_name: str, role_prompt: str) -> str:
        return (
                f"You are in a multi-person conversation setting. You are {role_name}."
                f"{role_prompt}"
                "Your task is to engage in conversations, provide opinions, and interact with other participants in a manner consistent with your role's identity setting. "
                "Based on the context of the conversation, cautiously assess whether you truly have something to say. "
                "If there is no need to speak, simply reply with a space. "
                "Before speaking, first ask the host 'Can I speak?'(send the literal phrase 'Can I speak?') and only speak after receiving permission. "
                "If granted the right to speak, directly state what you intend to say without making unrelated remarks such as thanking the host. "
                f"Please engage in the chat while adhering to these guidelines and staying in character as the '{role_name}'."
            )

    casperian_description = (
        "You always oppose others, skilled in sophistry and often harsh in your challenges, making you somewhat disliked. "
        "Your behavior is typically provocative, keen on finding faults in debates."
    )
    prompt_for_casperian = make_role_prompt(role_name="Casperian", role_prompt=casperian_description)
    amelie_description = (
        "You constantly praise others, even when it's inappropriate, struggling to discern right from wrong and overly accommodating. "
        "You tend to lack conviction, preferring to use compliments to gain others' favor."
    )
    prompt_for_amelie = make_role_prompt(role_name="Amelie", role_prompt=amelie_description)

    init_job.create_role(
        role=Role(name="Casperian", system_message=prompt_for_casperian),
        role_name="Casperian",
    )
    init_job.create_role(
        role=Role(name="Amelie", system_message=prompt_for_amelie),
        role_name="Amelie",
    )
    CommanderAsync().run_auto(init_job)
