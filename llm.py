import logging
import os
import time

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

MODEL = os.environ.get("MODEL", "qwen2.5:7b")

logger = logging.getLogger("masareef.llm")

client = OpenAI(
    api_key=os.environ.get("LLM_API_KEY", "ollama"),
    base_url=os.environ.get("LLM_BASE_URL", "http://localhost:11434/v1"),
    timeout=30,
    max_retries=1,
)

def chat(messages: list, tools: list) -> dict:
    started = time.perf_counter()
    response = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        tools=tools,
        temperature=0,
    )
    message = response.choices[0].message.model_dump(exclude_none=True)
    usage = response.usage
    # Token counts are what a paid provider bills on, so log them per call.
    logger.info(
        "llm model=%s ms=%d tokens_in=%s tokens_out=%s tool_calls=%d",
        MODEL,
        (time.perf_counter() - started) * 1000,
        usage.prompt_tokens if usage else "?",
        usage.completion_tokens if usage else "?",
        len(message.get("tool_calls") or []),
    )
    return message