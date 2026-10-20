"""Weekly spending report, sent to every allowed user in Telegram.

Run by cron on the server once a week. The numbers come straight from the
database; no model is involved, so the totals are always exact.
"""

import logging
import os
import sys

import httpx
from dotenv import load_dotenv

import db

load_dotenv()

ALLOWED = [int(x) for x in os.environ.get("ALLOWED_USERS", "").split(",") if x.strip()]

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("masareef.report")
for noisy in ("httpx", "httpx2", "httpcore"):
    logging.getLogger(noisy).setLevel(logging.WARNING)

NAMES = {
    "food": "أكل",
    "transport": "مواصلات",
    "shopping": "تسوق",
    "bills": "فواتير",
    "health": "صحة",
    "other": "أخرى",
}


def build(user_id: int) -> str:
    this_week = db.spending_by_category(user_id, 7)
    last_week = db.spending_by_category(user_id, 14, 7)
    total = sum(r["total"] for r in this_week)
    before = sum(r["total"] for r in last_week)

    if not this_week:
        return "تقريرك الأسبوعي:\nما سجّلت أي مصروف هالأسبوع."

    lines = [f"تقريرك الأسبوعي:\nالمجموع: {total:.2f} ريال"]
    if before:
        change = (total - before) / before * 100
        word = "أكثر" if change > 0 else "أقل"
        lines.append(f"{abs(change):.0f}% {word} من الأسبوع اللي قبله ({before:.2f})")

    lines.append("\nحسب التصنيف:")
    for r in this_week:
        lines.append(f"• {NAMES.get(r['category'], r['category'])}: {r['total']:.2f} ({r['count']})")

    lines.append("\nأكثر المتاجر:")
    for r in db.top_merchants(user_id, 7):
        lines.append(f"• {r['merchant']}: {r['total']:.2f}")
    return "\n".join(lines)


def send(user_id: int, text: str) -> None:
    httpx.post(
        f"https://api.telegram.org/bot{os.environ['TELEGRAM_TOKEN']}/sendMessage",
        json={"chat_id": user_id, "text": text},
        timeout=10,
    ).raise_for_status()


if __name__ == "__main__":
    # --dry-run prints the reports instead of sending them.
    dry = "--dry-run" in sys.argv
    db.init()
    for user_id in ALLOWED:
        text = build(user_id)
        if dry:
            print(f"--- {user_id}\n{text}\n")
            continue
        try:
            send(user_id, text)
            logger.info("report sent user=%s", user_id)
        except Exception:
            logger.exception("report failed user=%s", user_id)
