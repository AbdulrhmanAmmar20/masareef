import hashlib
import os
import secrets
import sqlite3

DB_PATH = os.environ.get("DB_PATH", "expenses.db")

def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init():
    with connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                amount REAL NOT NULL,
                merchant TEXT NOT NULL,
                category TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        # Keys for the SMS intake endpoint. Only a SHA-256 hash of each key is
        # stored, so a copy of the database cannot be used to send as a user.
        conn.execute("""
            CREATE TABLE IF NOT EXISTS api_tokens (
                token_hash TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)


def add_expense(user_id: int, amount: float, merchant: str, category: str) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO expenses (user_id, amount, merchant, category) VALUES (?, ?, ?, ?)",
            (user_id, amount, merchant, category),
        )

def total(user_id: int, category: str = "all") -> tuple[float, int]:
    query = "SELECT COALESCE(SUM(amount), 0), COUNT(*) FROM expenses WHERE user_id = ?"
    params = [user_id]
    if category != "all":
        query += " AND category = ?"
        params.append(category)
    with connect() as conn:
        return tuple(conn.execute(query, params).fetchone())


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_token(user_id: int) -> str:
    """Issue a new key for a user, replacing any key they had before."""
    token = secrets.token_urlsafe(32)
    with connect() as conn:
        conn.execute("DELETE FROM api_tokens WHERE user_id = ?", (user_id,))
        conn.execute(
            "INSERT INTO api_tokens (token_hash, user_id) VALUES (?, ?)",
            (_hash(token), user_id),
        )
    return token


def user_for_token(token: str) -> int | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT user_id FROM api_tokens WHERE token_hash = ?", (_hash(token),)
        ).fetchone()
    return row["user_id"] if row else None


if __name__ == "__main__":
    init()
    add_expense(1, 30.0, "ALBAIK", "food")
    add_expense(1, 120.0, "ALDREES", "transport")
    add_expense(2, 999.0, "OTHER USER", "food")
    print(total(1))
    print(total(1, "food"))