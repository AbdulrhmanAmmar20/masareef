import llm
import db
import json 

SYSTEM = """أنت مساعد لتتبع المصاريف الشخصية.
- رد دائمًا بالعربية وباختصار.
- إذا وصلتك رسالة بنك فيها عملية شراء، احفظها بالأداة المناسبة.
- المقاهي والمطاعم تصنيفها food.
- لا تخترع مبالغ أو عمليات غير موجودة في الرسالة.
- الوقود والبنزين ومحطات الوقود تصنيفها transport.
- لا تذكر أي مبلغ أو مجموع إلا بعد استدعاء الأداة في نفس الرد. لا تحسب من ذاكرتك.
- احفظ فقط إذا كانت الرسالة تأكيدًا لعملية شراء تمت فعلًا وخُصم مبلغها. لا تحفظ الإعلانات والعروض، ولا الاسترداد، ولا الإيداع، ولا رموز التحقق.
- الصيدليات والمستشفيات والعيادات تصنيفها health."""




CATEGORIES = ["food", "transport", "shopping", "bills", "health", "other"]

CATEGORIES = ["food", "transport", "shopping", "bills", "health", "other"]

SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "save_expense",
            "description": "Save one expense.",
            "parameters": {
                "type": "object",
                "properties": {
                    "amount": {"type": "number", "description": "The amount in SAR."},
                    "merchant": {"type": "string", "description": "Where the money was spent."},
                    "category": {"type": "string", "enum": CATEGORIES},
                },
                "required": ["amount", "merchant", "category"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_total",
            "description": "Get the total amount spent, in SAR.",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {"type": "string", "enum": CATEGORIES + ["all"]},
                },
                "required": ["category"],
            },
        },
    },
]




def make_tools(user_id: int) -> dict:
    def save_expense(amount: float, merchant: str, category: str) -> str:
        """Save one expense.

        Args:
            amount: The amount in SAR.
            merchant: Where the money was spent.
            category: One of: food, transport, shopping, bills, other.
        """

        db.add_expense(user_id, amount, merchant, category)

        return f"saved: {amount} SAR at {merchant} ({category})"


    def get_total(category:str = "all") -> str:
        """Get the total amount spent, in SAR.

        Args:
            category: One of: food, transport, shopping, bills, other, all.
        """

        total, count = db.total(user_id, category)

        return f"total: {total} SAR in {count} items for category {category}"

    return {"save_expense": save_expense, "get_total": get_total}




def trim(history: list, keep: int = 20) -> list:
    recent = history[-keep:]
    while recent and recent[0]["role"] != "user":
        recent.pop(0)
    return recent


def run(user_id: int, user_text: str, history: list) -> str:
    TOOLS = make_tools(user_id)
    messages = [
        {"role": "system", "content": SYSTEM},
        *trim(history),
        {"role": "user", "content": user_text},
    ]

    for step in range(5):

        message = llm.chat(messages, SCHEMAS)
        messages.append(message)

        if not message.get("tool_calls"):
            history.clear()
            history.extend(messages[1:])
            return message.get("content", "")

        for call in message["tool_calls"]:
            name = call["function"]["name"]
            args = json.loads(call["function"]["arguments"])
            print(f"step {step}: {name} {args}")
            if name not in TOOLS:
                result = f"error: unknown tool {name}"
            else:
                result = TOOLS[name](**args)
            messages.append({"role": "tool", "tool_call_id": call["id"], "content": result})

    return "stopped: too many steps"

db.init()


if __name__ == "__main__":
    db.init()
    history = []
    while True:
        text = input("> ")
        if text == "exit":
            break
        print(run(1, text, history))