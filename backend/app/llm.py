from openai import AsyncOpenAI

from .config import settings

client = AsyncOpenAI(
    base_url=settings.llama_base_url,
    api_key="not-used",
)


async def chat(messages, tools=None, tool_choice="auto"):
    kwargs = {
        "model": settings.llama_model,
        "messages": messages,
        "temperature": 0.2,
        "extra_body": {"chat_template_kwargs": {"enable_thinking": False}},
    }
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = tool_choice
    return await client.chat.completions.create(**kwargs)
