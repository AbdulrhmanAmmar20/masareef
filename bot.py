import os
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, MessageHandler, ContextTypes, filters
import asyncio
import db
from agent import run

load_dotenv()
HISTORIES = {}


async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    history = HISTORIES.setdefault(user_id, [])
    reply = await asyncio.to_thread(run, user_id, text, history)
    await update.message.reply_text(reply)

db.init()

app = Application.builder().token(os.environ["TELEGRAM_TOKEN"]).build()
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))
app.run_polling()