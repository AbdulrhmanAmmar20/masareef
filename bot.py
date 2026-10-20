import asyncio
import logging
import os
import time

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

import db
from graph_agent import run

load_dotenv()

ALLOWED = {int(x) for x in os.environ.get("ALLOWED_USERS", "").split(",") if x.strip()}

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("masareef")
# The HTTP client logs every request URL at INFO. Telegram puts the bot token
# in the URL, so these loggers must stay quiet or the token ends up in the logs.
for noisy in ("httpx", "httpx2", "httpcore"):
    logging.getLogger(noisy).setLevel(logging.WARNING)

WELCOME = (
    "أهلًا! أنا أتتبع مصاريفك.\n\n"
    "• أرسل لي رسالة البنك بعد أي عملية شراء وأحفظها.\n"
    "• اسألني مثل: كم صرفت على الأكل؟\n\n"
    "التجربة الحين برسايل وهمية بس. لا ترسل رسايل بنكك الحقيقية."
)


async def on_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ALLOWED:
        # Shows the id so the person can send it to the owner to be added.
        await update.message.reply_text(
            f"البوت خاص حاليًا. أرسل هذا الرقم لصاحب البوت عشان يضيفك:\n{user_id}"
        )
        return
    await update.message.reply_text(WELCOME)


async def on_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Issue the key the iPhone automation uses to send bank SMS."""
    user_id = update.effective_user.id
    if user_id not in ALLOWED:
        await update.message.reply_text("هذا البوت خاص. أرسل /start لتعرف رقمك.")
        return
    # A new key replaces the old one, so /link also revokes a leaked key.
    token = db.create_token(user_id)
    logger.info("link user=%s issued a new key", user_id)
    await update.message.reply_text(
        "هذا مفتاحك لأتمتة الآيفون. انسخه وحطه في الاختصار:\n\n"
        f"{token}\n\n"
        "لا تشاركه مع أحد. أي أحد معه هذا المفتاح يقدر يرسل رسايل باسمك.\n"
        "لو تسرّب، أرسل /link مرة ثانية ويتلغى القديم."
    )


async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ALLOWED:
        await update.message.reply_text("هذا البوت خاص. أرسل /start لتعرف رقمك.")
        return
    text = update.message.text
    started = time.perf_counter()
    ok = True
    try:
        # Conversation history is saved by the LangGraph checkpointer, per user.
        reply = await asyncio.to_thread(run, user_id, text, [])
    except Exception:
        # Full details go to the container log; the user gets a generic message
        # so internal details (files, provider errors) are never shown to them.
        logger.exception("agent failed for user %s", user_id)
        reply = "صار خطأ مؤقت عندي. حاول مرة ثانية بعد دقيقة."
        ok = False
    logger.info("request user=%s ms=%d ok=%s", user_id, (time.perf_counter() - started) * 1000, ok)
    # Telegram rejects empty messages, so never send one.
    await update.message.reply_text(reply or "ما فهمت الرسالة، جرّب تكتبها بشكل ثاني.")


db.init()

app = Application.builder().token(os.environ["TELEGRAM_TOKEN"]).build()
app.add_handler(CommandHandler("start", on_start))
app.add_handler(CommandHandler("link", on_link))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))
app.run_polling()
