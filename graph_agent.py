import json
import operator
import os
import sqlite3
from typing import Annotated
from typing_extensions import TypedDict

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import StateGraph, START, END

import db
import llm
from agent import SYSTEM, SCHEMAS, make_tools, trim
from privacy import redact

MAX_STEPS = 5

class State(TypedDict):
    messages: Annotated[list, operator.add]
    user_id: int
    steps: int


def call_model(state: State) -> dict:
    # The saved conversation holds only user/assistant/tool messages. The system
    # prompt is added at send time so it is never duplicated in the saved state.
    message = llm.chat(
        [{"role": "system", "content": SYSTEM}, *trim(state["messages"])],
        SCHEMAS,
    )
    return {"messages": [message], "steps": state["steps"] + 1}


def run_tools(state: State) -> dict:
    tools = make_tools(state["user_id"])
    last = state["messages"][-1]
    results = []
    for call in last["tool_calls"]:
        name = call["function"]["name"]
        args = json.loads(call["function"]["arguments"])
        if name not in tools:
            result = f"error: unknown tool {name}"
        else:
            result = tools[name](**args)
        results.append({"role": "tool", "tool_call_id": call["id"], "content": result})
    return {"messages": results}


def route(state: State) -> str:
    last = state["messages"][-1]
    if last.get("tool_calls") and state["steps"] < MAX_STEPS:
        return "run_tools"
    return END


builder = StateGraph(State)
builder.add_node("call_model", call_model)
builder.add_node("run_tools", run_tools)

builder.add_edge(START, "call_model")
builder.add_conditional_edges("call_model", route)
builder.add_edge("run_tools", "call_model")

# Conversations are saved next to the expenses database, so in the container
# they live on the persistent volume and survive redeploys.
CHECKPOINTS = os.path.join(os.path.dirname(os.path.abspath(db.DB_PATH)), "checkpoints.db")
checkpointer = SqliteSaver(sqlite3.connect(CHECKPOINTS, check_same_thread=False))
graph = builder.compile(checkpointer=checkpointer)


def run(user_id: int, user_text: str, history: list) -> str:
    # Strip card digits, balances, IBANs and codes before anything else sees
    # the text: the model provider, the saved conversation, and the logs.
    user_text = redact(user_text)
    # Only the new message is sent in; LangGraph loads the earlier conversation
    # for this thread from the checkpointer and appends to it.
    result = graph.invoke(
        {
            "messages": [{"role": "user", "content": user_text}],
            "user_id": user_id,
            "steps": 0,
        },
        config={"configurable": {"thread_id": str(user_id)}},
    )
    messages = result["messages"]
    # Kept in sync for callers that inspect it (the evals); the saved
    # conversation in the checkpointer is the source of truth.
    history.clear()
    history.extend(messages)
    last = messages[-1]
    if last.get("tool_calls"):
        return "stopped: too many steps"
    return last.get("content", "")