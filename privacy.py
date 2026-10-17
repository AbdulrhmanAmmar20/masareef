import re

RULES = [
    # IBAN: SA followed by 22 digits/letters, possibly spaced
    (re.compile(r"\bSA\d{2}(?:\s?[0-9A-Z]){18,22}\b"), "[iban]"),
    # Masked card digits: **4821, xx4821, ****4821
    (re.compile(r"(?:\*+|[xX]{2,})\s?\d{2,4}"), "[card]"),
    # Balance lines: الرصيد / رصيد / المتاح followed by a number
    (re.compile(r"(الرصيد|رصيد|المتاح)([^\n\d]{0,15})[\d,٬.٫]+"), r"\1\2[balance]"),
    # Verification codes: رمز ... followed by 4-8 digits
    (re.compile(r"(رمز[^\n\d]{0,20})\d{4,8}"), r"\1[code]"),
    # Any long digit run: account numbers, IDs
    (re.compile(r"\b\d{8,}\b"), "[number]"),
]


def redact(text: str) -> str:
    for pattern, replacement in RULES:
        text = pattern.sub(replacement, text)
    return text


if __name__ == "__main__":
    cases = [
        "شراء عبر مدى\nبطاقة: **4821\nمبلغ: 45.50 SAR\nلدى: STARBUCKS\nالرصيد: 12,340.75 SAR",
        "تحويل إلى SA03 8000 0000 6080 1016 7519",
        "رمز التحقق 482913 لا تشاركه مع أحد",
        "رقم الحساب 0123456789012",
        "شريت بنزين بمئة من الدريس",
    ]
    for text in cases:
        print(redact(text))
        print("---")