"""SQLite storage for expenses."""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


def default_db_path() -> Path:
    env = os.environ.get("FINTRACKER_DB_PATH", "").strip()
    if env:
        return Path(env).expanduser()
    return Path(__file__).resolve().parent.parent / "data" / "expenses.db"


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


@contextmanager
def connect(db_path: Path | None = None) -> Iterator[sqlite3.Connection]:
    path = db_path or default_db_path()
    ensure_parent(path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        init_schema(conn)
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            amount INTEGER NOT NULL,
            currency TEXT NOT NULL DEFAULT 'IDR',
            category TEXT,
            note TEXT NOT NULL DEFAULT '',
            source TEXT,
            attributed_to TEXT,
            created_at TEXT NOT NULL
        )
        """
    )
    cols = {row[1] for row in conn.execute("PRAGMA table_info(expenses)")}
    if "attributed_to" not in cols:
        conn.execute("ALTER TABLE expenses ADD COLUMN attributed_to TEXT")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_expenses_user_created "
        "ON expenses (user_id, created_at DESC)"
    )


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def add_expense(
    conn: sqlite3.Connection,
    *,
    user_id: str,
    amount: int,
    category: str | None,
    note: str,
    source: str | None = None,
    currency: str = "IDR",
    created_at: str | None = None,
    attributed_to: str | None = None,
) -> dict[str, Any]:
    ts = created_at or now_iso()
    cur = conn.execute(
        """
        INSERT INTO expenses (user_id, amount, currency, category, note, source, attributed_to, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (user_id, amount, currency, category, note, source, attributed_to, ts),
    )
    row_id = cur.lastrowid
    row = conn.execute("SELECT * FROM expenses WHERE id = ?", (row_id,)).fetchone()
    return dict(row)


def list_expenses(
    conn: sqlite3.Connection,
    *,
    user_id: str,
    limit: int = 20,
    month: str | None = None,
) -> list[dict[str, Any]]:
    query = "SELECT * FROM expenses WHERE user_id = ?"
    params: list[Any] = [user_id]
    if month:
        query += " AND created_at LIKE ?"
        params.append(f"{month}%")
    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


def summary_expenses(
    conn: sqlite3.Connection,
    *,
    user_id: str,
    month: str | None = None,
) -> dict[str, Any]:
    query = (
        "SELECT COALESCE(SUM(amount), 0) AS total, COUNT(*) AS count "
        "FROM expenses WHERE user_id = ?"
    )
    params: list[Any] = [user_id]
    if month:
        query += " AND created_at LIKE ?"
        params.append(f"{month}%")
    row = conn.execute(query, params).fetchone()

    by_cat_query = (
        "SELECT COALESCE(category, 'lainnya') AS category, SUM(amount) AS total, COUNT(*) AS count "
        "FROM expenses WHERE user_id = ?"
    )
    cat_params: list[Any] = [user_id]
    if month:
        by_cat_query += " AND created_at LIKE ?"
        cat_params.append(f"{month}%")
    by_cat_query += " GROUP BY category ORDER BY total DESC"
    by_cat = conn.execute(by_cat_query, cat_params).fetchall()

    return {
        "total": int(row["total"]),
        "count": int(row["count"]),
        "by_category": [dict(r) for r in by_cat],
    }


def delete_expense(conn: sqlite3.Connection, *, expense_id: int, user_id: str) -> bool:
    cur = conn.execute(
        "DELETE FROM expenses WHERE id = ? AND user_id = ?",
        (expense_id, user_id),
    )
    return cur.rowcount > 0


def get_expense_by_id(
    conn: sqlite3.Connection, *, expense_id: int, user_id: str
) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT * FROM expenses WHERE id = ? AND user_id = ?",
        (expense_id, user_id),
    ).fetchone()
    return dict(row) if row else None


def get_last_expense(conn: sqlite3.Connection, *, user_id: str) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT * FROM expenses WHERE user_id = ? ORDER BY created_at DESC LIMIT 1",
        (user_id,),
    ).fetchone()
    return dict(row) if row else None
