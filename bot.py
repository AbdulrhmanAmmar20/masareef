import asyncio
import logging
import os

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

import db
from graph_agent import run

load_dotenv()

ALLOWED = {int(x) for x in os.environ.get("ALLOWED_USERS", "").split(",") if x.strip()}

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("masareef")

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


async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ALLOWED:
        await update.message.reply_text("هذا البوت خاص. أرسل /start لتعرف رقمك.")
        return
    text = update.message.text
    try:
        # Conversation history is saved by the LangGraph checkpointer, per user.
        reply = await asyncio.to_thread(run, user_id, text, [])
    except Exception:
        # Full details go to the container log; the user gets a generic message
        # so internal details (files, provider errors) are never shown to them.
        logger.exception("agent failed for user %s", user_id)
        reply = "صار خطأ مؤقت عندي. حاول مرة ثانية بعد دقيقة."
    # Telegram rejects empty messages, so never send one.
    await update.message.reply_text(reply or "ما فهمت الرسالة، جرّب تكتبها بشكل ثاني.")


db.init()

app = Application.builder().token(os.environ["TELEGRAM_TOKEN"]).build()
app.add_handler(CommandHandler("start", on_start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))
app.run_polling()
