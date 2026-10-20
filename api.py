"""HTTP intake for bank SMS forwarded by an iPhone Shortcuts automation.

POST /sms with a JSON body {"text": "..."} and the header
"Authorization: Bearer <key>". The key comes from the bot's /link command.
The message goes through the same agent as Telegram messages, and the
result is sent back to the user in Telegram.
"""

import logging
import os
import time

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

import db
from graph_agent import run

load_dotenv()

ALLOWED = {int(x) for x in os.environ.get("ALLOWED_USERS", "").split(",") if x.strip()}
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("masareef.api")
# Same reason as in bot.py: the Telegram URL contains the bot token.
for noisy in ("httpx", "httpx2", "httpcore"):
    logging.getLogger(noisy).setLevel(logging.WARNING)

# No interactive docs or schema on a public endpoint.
app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
db.init()


class SMS(BaseModel):
    # Bank SMS are short; the cap stops anyone sending huge bodies to the model.
    text: str = Field(min_length=1, max_length=2000)


def notify(user_id: int, text: str) -> None:
    """Send a message to the user's private chat with the bot."""
    httpx.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        json={"chat_id": user_id, "text": text},
        timeout=10,
    )


@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.post("/sms")
def receive_sms(sms: SMS, authorization: str = Header(default="")) -> dict:
    token = authorization.removeprefix("Bearer ").strip()
    user_id = db.user_for_token(token) if token else None
    # The same answer for a wrong key and a removed user, so the response
    # does not reveal which keys exist.
    if user_id is None or user_id not in ALLOWED:
        raise HTTPException(status_code=401, detail="unauthorized")

    started = time.perf_counter()
    try:
        reply = run(user_id, sms.text, [])
    except Exception:
        logger.exception("agent failed for sms from user %s", user_id)
        raise HTTPException(status_code=503, detail="try again later")
    logger.info("sms user=%s ms=%d", user_id, (time.perf_counter() - started) * 1000)

    notify(user_id, f"من رسالة البنك:\n{reply or 'ما قدرت أقرأ الرسالة.'}")
    return {"ok": True}
