import json
import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Optional

DB_PATH = Path(__file__).parent.parent / "runtime" / "chefmate.db"


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS conversations (
            id TEXT PRIMARY KEY,
            query TEXT NOT NULL,
            rewritten_query TEXT,
            route_type TEXT,
            answer TEXT NOT NULL,
            confidence REAL,
            sources_json TEXT,
            retrieval_count INTEGER,
            elapsed_ms REAL,
            feedback INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS api_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ip TEXT NOT NULL,
            query_hash TEXT NOT NULL,
            route_type TEXT,
            elapsed_ms REAL,
            error TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_conversations_created
            ON conversations(created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_api_logs_ip ON api_logs(ip);
        CREATE INDEX IF NOT EXISTS idx_api_logs_time ON api_logs(created_at);
    """)
    conn.commit()
    conn.close()


def save_conversation(
    conv_id: str,
    query: str,
    answer: str,
    rewritten_query: str = "",
    route_type: str = "",
    confidence: Optional[float] = None,
    sources_json: str = "",
    retrieval_count: int = 0,
    elapsed_ms: float = 0,
):
    conn = get_connection()
    conn.execute(
        """INSERT OR REPLACE INTO conversations
           (id, query, rewritten_query, route_type, answer,
            confidence, sources_json, retrieval_count, elapsed_ms)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (conv_id, query, rewritten_query, route_type, answer,
         confidence, sources_json, retrieval_count, elapsed_ms),
    )
    conn.commit()
    conn.close()


def get_history(limit: int = 50) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, query, answer, route_type, confidence, created_at "
        "FROM conversations ORDER BY created_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def save_feedback(conv_id: str, feedback: int) -> bool:
    conn = get_connection()
    cur = conn.execute(
        "UPDATE conversations SET feedback=? WHERE id=?",
        (feedback, conv_id),
    )
    ok = cur.rowcount > 0
    conn.commit()
    conn.close()
    return ok


def log_api_call(ip: str, query_hash: str, route_type: str, elapsed_ms: float, error: str = ""):
    conn = get_connection()
    conn.execute(
        "INSERT INTO api_logs (ip, query_hash, route_type, elapsed_ms, error) VALUES (?, ?, ?, ?, ?)",
        (ip, query_hash, route_type, elapsed_ms, error),
    )
    conn.commit()
    conn.close()


def count_calls_today() -> int:
    conn = get_connection()
    row = conn.execute(
        "SELECT COUNT(*) as cnt FROM api_logs WHERE date(created_at)=date('now')",
    ).fetchone()
    conn.close()
    return row["cnt"] if row else 0


def count_calls_this_month() -> int:
    conn = get_connection()
    row = conn.execute(
        "SELECT COUNT(*) as cnt FROM api_logs WHERE strftime('%Y-%m', created_at)=strftime('%Y-%m', 'now')",
    ).fetchone()
    conn.close()
    return row["cnt"] if row else 0
