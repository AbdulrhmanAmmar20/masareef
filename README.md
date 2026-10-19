# Masareef

A Telegram bot that tracks personal expenses from bank SMS messages. You forward a purchase message, an LLM agent extracts the amount, merchant and category and saves it, and you can then ask questions like "how much did I spend on food?" in Arabic.

The agent loop, tools, evals and deployment were written by hand to learn how agents work end to end, from tool calling to a running service.

## How it works

```
Telegram  ->  bot.py  ->  privacy.redact()  ->  LangGraph agent  ->  LLM (OpenAI-compatible API)
                                                      |
                                               tools: save_expense, get_total
                                                      |
                                               SQLite (expenses + saved conversations)
```

1. **bot.py** receives a message, checks the sender against an allowlist, and passes the text to the agent.
2. **privacy.py** strips card digits, balances, IBANs, verification codes and long account numbers before the text reaches the model or the saved conversation.
3. **graph_agent.py** runs a two-node LangGraph graph: `call_model` asks the LLM what to do, `run_tools` executes the requested tools, and a conditional edge loops between them until the model answers (capped at 5 steps).
4. Tools are scoped to the sender: `make_tools(user_id)` binds the Telegram user id inside the tool functions, so the model never sees or chooses whose data it touches.
5. Conversations are saved per user by a SQLite checkpointer, so the bot keeps context across restarts and redeploys.

## Project layout

| File | Purpose |
|---|---|
| `bot.py` | Telegram bot (long polling), allowlist check |
| `graph_agent.py` | LangGraph agent with persistent conversations (used by the bot) |
| `agent.py` | The original hand-written agent loop, plus the system prompt, tool schemas and tool functions shared by both agents |
| `llm.py` | Single entry point to the model through any OpenAI-compatible endpoint |
| `privacy.py` | Redaction rules applied to every incoming message |
| `db.py` | SQLite storage for expenses, isolated per user |
| `evals.py` | Tool-choice and full-conversation evals |
| `Dockerfile`, `compose.yaml` | Container image and runtime configuration |
| `deploy.sh` | Pull-based deploy script run by cron on the server |
| `.github/workflows/ci.yml` | CI: syntax check, image build, import check inside the image |

## Tools

| Tool | What it does |
|---|---|
| `save_expense(amount, merchant, category)` | Saves one expense in SAR |
| `get_total(category)` | Returns the total spent, for one category or `all` |

Categories: `food`, `transport`, `shopping`, `bills`, `health`, `other`.

## Running locally

Requirements: Python 3.12, and either [Ollama](https://ollama.com) or an API key for an OpenAI-compatible provider.

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
```

Create a `.env` file:

```
TELEGRAM_TOKEN=your-bot-token
ALLOWED_USERS=your-telegram-user-id

# Model. Leave these three out to use a local Ollama model (qwen2.5:7b).
LLM_API_KEY=your-api-key
LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
MODEL=gemini-3.5-flash-lite
```

To use a local model instead:

```bash
ollama pull qwen2.5:7b
```

Start the bot:

```bash
python bot.py
```

Or chat with the agent in the terminal without Telegram:

```bash
python agent.py
```

## Configuration

| Variable | Default | Notes |
|---|---|---|
| `TELEGRAM_TOKEN` | required | From BotFather |
| `ALLOWED_USERS` | empty | Comma-separated Telegram user ids. Empty means nobody is allowed |
| `LLM_BASE_URL` | `http://localhost:11434/v1` | Any OpenAI-compatible endpoint |
| `LLM_API_KEY` | `ollama` | Not needed for a local model |
| `MODEL` | `qwen2.5:7b` | Pinned in `compose.yaml` for the deployed bot |
| `DB_PATH` | `expenses.db` | Conversations are saved in `checkpoints.db` next to it |

Secrets live in `.env`, which is ignored by git and by Docker. Non-secret settings such as the model version live in `compose.yaml`, so changes to them are reviewed, versioned and deployed like code.

## Evals

```bash
python evals.py
```

The suite has two parts and uses a throwaway database:

- **Tool choice (11 cases):** sends a single message and checks the first tool the model asks for and its arguments. Covers purchases, questions about totals, and messages that must not be saved: salary deposits, refunds, ads and verification codes.
- **Conversations (5 cases):** runs the real agent loop over one or more turns and checks the final reply: required tool calls happened, no number appears without a tool call in the same turn, no language switching, and a balance sent in a message is never repeated back (it should have been redacted).

Useful options:

```bash
AGENT_MODULE=graph_agent python evals.py   # test the LangGraph agent instead of the hand-written loop
EVAL_DELAY=4 python evals.py               # wait between calls on rate-limited free tiers
```

Results on the current suite:

| Model | Tool choice | Conversations |
|---|---|---|
| `gemini-3.5-flash-lite` | 11/11 | 5/5 |
| `qwen2.5:7b` (local) | 11/11 | 5/5 |

In manual multi-turn testing the local 7B model occasionally switched to Chinese mid-reply or stated a total without calling the tool. These failures are intermittent, which is why the conversation evals check for them explicitly.

## Deployment

The bot runs on a small AWS EC2 instance (Ubuntu) with Docker Compose.

- **Container:** the image contains the code and dependencies only. Secrets come from `.env` on the server, and both SQLite files live on a named volume, so data survives rebuilds.
- **Restart policy:** `restart: unless-stopped` brings the bot back after a crash or a server reboot.
- **CI:** every push builds the image and imports the agent inside it, which catches files missing from the `COPY` line before they reach the server.
- **Continuous deployment:** `deploy.sh` runs every five minutes from cron. It fetches `master`, and if the commit changed it pulls and rebuilds. The server pulls rather than being pushed to, so no inbound access is needed for deploys.

```
*/5 * * * * /home/ubuntu/masareef/deploy.sh >> /home/ubuntu/deploy.log 2>&1
```

## Privacy

- Card digits, balances, IBANs, verification codes and long account numbers are removed before text reaches the model or is saved.
- The bot is closed to everyone except the ids in `ALLOWED_USERS`. The sender id comes from Telegram, not from the message text.
- Messages still pass through Telegram, and the remaining text is sent to the model provider. Free API tiers may use data to improve their products, so only use test data on a free tier.

## Known limitations

- `deploy.sh` deploys any commit on `master`, including one whose CI failed.
- No backups yet: the expenses and conversations exist only on the server's volume.
- Redaction rules cover common bank SMS formats and need testing against each bank's real format.
- Conversations are stored in full and grow without limit; only the last 20 messages are sent to the model.

## Roadmap

- Daily backups of both databases to S3, and SSH replaced by AWS Systems Manager Session Manager
- Run evals several times per case and report a pass rate instead of a single pass or fail
- Automatic intake of bank SMS from an iPhone via a Shortcuts automation
- Self-hosting the model with vLLM on a GPU instance and comparing cost and latency against the API
