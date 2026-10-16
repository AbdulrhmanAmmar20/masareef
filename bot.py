import os
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, MessageHandler, ContextTypes, filters
import asyncio
import db
from graph_agent import run

load_dotenv()

ALLOWED = {int(x) for x in os.environ.get("ALLOWED_USERS", "").split(",") if x.strip()}

async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ALLOWED:
        await update.message.reply_text("هذا البوت خاص.")
        return
    text = update.message.text
    # Conversation history is saved by the LangGraph checkpointer, per user.
    reply = await asyncio.to_thread(run, user_id, text, [])
    await update.message.reply_text(reply)

db.init()

app = Application.builder().token(os.environ["TELEGRAM_TOKEN"]).build()
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))
app.run_polling()