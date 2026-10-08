import os
import ollama

MODEL = os.environ.get("MODEL", "qwen2.5:7b")

def chat(messages: list, tools: list):
    response = ollama.chat(
        model=MODEL,
        messages=messages,
        tools=tools,
        options={"temperature": 0},
    )
    return response.message