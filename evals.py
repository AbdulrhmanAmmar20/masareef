import llm
from agent import SYSTEM, make_tools

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
    ("شراء عبر مدى\nمبلغ: 62 SAR\nلدى: NAHDI PHARMACY", "save_expense", {"amount": 62, "category": "health"}),]


def first_call(text: str):
    message = llm.chat(
        [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": text},
        ],
        list(make_tools(0).values()),
    )
    calls = message.tool_calls or []
    if not calls:
        return None, {}
    return calls[0].function.name, calls[0].function.arguments


passed = 0
for text, expected_name, expected_args in CASES:
    name, args = first_call(text)
    ok = name == expected_name and all(args.get(k) == v for k, v in expected_args.items())
    passed += ok
    print("PASS" if ok else "FAIL", "|", text[:30].replace("\n", " "), "|", name, args)

print(f"\n{passed}/{len(CASES)} passed")