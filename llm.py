import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

MODEL = os.environ.get("MODEL", "qwen2.5:7b")

client = OpenAI(
    api_key=os.environ.get("LLM_API_KEY", "ollama"),
    base_url=os.environ.get("LLM_BASE_URL", "http://localhost:11434/v1"),
    timeout=30,
    max_retries=1,
)

def chat(messages: list, tools: list) -> dict:
    response = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        tools=tools,
        temperature=0,
    )
    return response.choices[0].message.model_dump(exclude_none=True)