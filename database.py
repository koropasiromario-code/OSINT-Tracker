import json
import os
import sqlite3
from pathlib import Path

DB_PATH = Path(os.environ.get("OSINT_DB_PATH", "data/osint.db"))
DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def get_connection():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def initialize_database():
    with get_connection() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT, target TEXT NOT NULL,
            collected_at TEXT NOT NULL, content_json TEXT NOT NULL)""")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_snapshots_target_time ON snapshots(target, collected_at DESC)")


def save_snapshot(target: str, content: dict):
    with get_connection() as conn:
        conn.execute("INSERT INTO snapshots (target, collected_at, content_json) VALUES (?, ?, ?)",
                     (target, content["collected_at"], json.dumps(content, ensure_ascii=False)))


def get_snapshots(target: str, limit: int = 50) -> list[dict]:
    limit = max(1, min(int(limit), 500))
    with get_connection() as conn:
        rows = conn.execute("SELECT id, target, collected_at, content_json FROM snapshots WHERE target = ? ORDER BY id DESC LIMIT ?",
                            (target, limit)).fetchall()
    return [{"id": r["id"], "target": r["target"], "collected_at": r["collected_at"],
             "content": json.loads(r["content_json"])} for r in rows]
