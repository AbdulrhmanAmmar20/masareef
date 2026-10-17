import contextlib
import io
import json
import os
import re
import tempfile
import time

# Conversation evals write expenses, so they get a throwaway database.
# This must be set before importing agent/db, which read DB_PATH on import.
os.environ["DB_PATH"] = os.path.join(tempfile.mkdtemp(), "evals.db")

import importlib  # noqa: E402

import llm  # noqa: E402
from agent import SCHEMAS, SYSTEM  # noqa: E402

# Which agent implementation the conversation evals run: "agent" (hand-written
# loop) or "graph_agent" (LangGraph). Both expose the same run() signature.
AGENT_MODULE = os.environ.get("AGENT_MODULE", "agent")
run = importlib.import_module(AGENT_MODULE).run

# Seconds to wait between model calls. Free API tiers limit requests per minute.
DELAY = float(os.environ.get("EVAL_DELAY", "0"))


# ---------------------------------------------------------------------------
# Part 1: tool choice - one message, check the first tool the model asks for.
# ---------------------------------------------------------------------------

CASES = [
    ("شراء عبر مدى\nمبلغ: 45.50 SAR\nلدى: STARBUCKS", "save_expense", {"amount": 45.5, "category": "food"}),
    ("شريت بنزين بمئة من الدريس", "save_expense", {"amount": 100, "category": "transport"}),
    ("كم صرفت على الأكل؟", "get_total", {"category": "food"}),
    ("كم صرفت كلي؟", "get_total", {"category": "all"}),
    ("السلام عليكم", None, {}),
    ("تم إيداع راتب\nمبلغ: 9000 SAR\nمن: ARAMCO", None, {}),
    ("رمز التحقق 482913 لا تشاركه مع أحد", None, {}),
    ("عرض خاص! خصم 50% لدى نون، اشتر الآن بـ 199 ريال فقط", None, {}),
    ("استرداد مبلغ\nمبلغ: 45.50 SAR\nمن: STARBUCKS", None, {}),
    ("شراء إنترنت\nمبلغ: 39.99 SAR\nلدى: NETFLIX", "save_expense", {"amount": 39.99, "category": "bills"}),
    ("شراء عبر مدى\nمبلغ: 62 SAR\nلدى: NAHDI PHARMACY", "save_expense", {"amount": 62, "category": "health"}),
]


def first_call(text: str):
    message = llm.chat(
        [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": text},
        ],
        SCHEMAS,
    )
    calls = message.get("tool_calls") or []
    if not calls:
        return None, {}
    return calls[0]["function"]["name"], json.loads(calls[0]["function"]["arguments"])


def run_tool_choice() -> tuple[int, int]:
    passed = 0
    for text, expected_name, expected_args in CASES:
        time.sleep(DELAY)
        name, args = first_call(text)
        ok = name == expected_name and all(args.get(k) == v for k, v in expected_args.items())
        passed += ok
        print("PASS" if ok else "FAIL", "|", text[:30].replace("\n", " "), "|", name, args)
    return passed, len(CASES)


# ---------------------------------------------------------------------------
# Part 2: conversations - run the real agent loop and check the final reply.
#
# Each turn lists the tools it must call (name + the arguments that matter)
# and strings the reply must contain. Every turn is also checked for:
#   - a non-empty reply
#   - no Chinese characters (the local model sometimes switches language)
#   - no number in the reply unless a tool was called in that same turn
# ---------------------------------------------------------------------------

CONVERSATIONS = [
    {
        "name": "save then total in one message",
        "turns": [
            {
                "user": "شريت قهوة بعشرين من دانكن، وكم صار مجموع الأكل بعدها؟",
                "tools": [("save_expense", {"amount": 20, "category": "food"}), ("get_total", {"category": "food"})],
                "contains": ["20|عشرين"],
            },
        ],
    },
    {
        "name": "total after several turns",
        "turns": [
            {"user": "شريت قهوة بعشرين من دانكن", "tools": [("save_expense", {"amount": 20})], "contains": []},
            {"user": "وشريت بنزين بمئة من الدريس", "tools": [("save_expense", {"amount": 100, "category": "transport"})], "contains": []},
            {"user": "كم صرفت كلي؟", "tools": [("get_total", {"category": "all"})], "contains": ["120|مئة وعشرين|مائة وعشرين"]},
        ],
    },
    {
        "name": "follow-up question uses context",
        "turns": [
            {"user": "شراء عبر مدى\nمبلغ: 45.50 SAR\nلدى: STARBUCKS", "tools": [("save_expense", {"amount": 45.5})], "contains": []},
            {"user": "كم صرفت على الأكل؟", "tools": [("get_total", {"category": "food"})], "contains": ["45.5|٤٥٫٥"]},
            {"user": "والمواصلات؟", "tools": [("get_total", {"category": "transport"})], "contains": []},
        ],
    },
    {
        "name": "greeting needs no tool",
        "turns": [
            {"user": "السلام عليكم", "tools": [], "contains": []},
        ],
    },
    {
        "name": "balance never reaches the model",
        "turns": [
            {
                "user": "شراء عبر مدى\nبطاقة: **4821\nمبلغ: 45.50 SAR\nلدى: STARBUCKS\nالرصيد: 12,340.75 SAR",
                "tools": [("save_expense", {"amount": 45.5})],
                "contains": [],
            },
            {"user": "كم رصيدي في البنك؟", "tools": [], "contains": []},
        ],
    },
]

CHINESE = re.compile(r"[一-鿿]")
DIGIT = re.compile(r"[0-9٠-٩]")


def calls_this_turn(history: list) -> list[tuple[str, dict]]:
    """Tool calls made after the last user message in the history."""
    last_user = max(i for i, m in enumerate(history) if m.get("role") == "user")
    calls = []
    for message in history[last_user + 1 :]:
        for call in message.get("tool_calls") or []:
            calls.append((call["function"]["name"], json.loads(call["function"]["arguments"])))
    return calls


def check_turn(turn: dict, reply: str, calls: list[tuple[str, dict]]) -> list[str]:
    problems = []
    if not reply.strip():
        problems.append("empty reply")
    if CHINESE.search(reply):
        problems.append("reply contains Chinese")
    if DIGIT.search(reply) and not calls:
        problems.append("number in reply without any tool call")
    for name, args in turn["tools"]:
        if not any(n == name and all(a.get(k) == v for k, v in args.items()) for n, a in calls):
            problems.append(f"missing tool call {name} {args}")
    if not turn["tools"] and calls:
        problems.append(f"unexpected tool calls {[n for n, _ in calls]}")
    normalized = reply.replace(",", "")
    # "a|b" means either form is fine: models write numbers as digits or words.
    for expected in turn["contains"]:
        if not any(option in normalized for option in expected.split("|")):
            problems.append(f"reply missing '{expected}'")
    return problems


def run_conversations() -> tuple[int, int]:
    passed = 0
    for number, convo in enumerate(CONVERSATIONS, start=1):
        user_id = 1000 + number  # each conversation gets its own empty account
        history: list = []
        problems = []
        for turn in convo["turns"]:
            time.sleep(DELAY)
            try:
                with contextlib.redirect_stdout(io.StringIO()):  # hide the agent's step prints
                    reply = run(user_id, turn["user"], history)
            except Exception as exc:
                problems.append(f"crashed: {type(exc).__name__}: {str(exc)[:120]}")
                break
            calls = calls_this_turn(history) if history else []
            for problem in check_turn(turn, reply, calls):
                problems.append(f"turn '{turn['user'][:20]}': {problem}")
        ok = not problems
        passed += ok
        print("PASS" if ok else "FAIL", "|", convo["name"])
        for problem in problems:
            print("      -", problem)
    return passed, len(CONVERSATIONS)


if __name__ == "__main__":
    print("model:", llm.MODEL, "| agent:", AGENT_MODULE)

    started = time.time()
    print("\n== tool choice ==")
    tool_passed, tool_total = run_tool_choice()
    print("\n== conversations ==")
    convo_passed, convo_total = run_conversations()

    print(f"\ntool choice:   {tool_passed}/{tool_total}")
    print(f"conversations: {convo_passed}/{convo_total}")
    print(f"time: {time.time() - started:.1f}s")
