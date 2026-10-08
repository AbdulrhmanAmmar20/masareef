import os
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



if __name__ == "__main__":
    init()
    add_expense(1, 30.0, "ALBAIK", "food")
    add_expense(1, 120.0, "ALDREES", "transport")
    add_expense(2, 999.0, "OTHER USER", "food")
    print(total(1))
    print(total(1, "food"))