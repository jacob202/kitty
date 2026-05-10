# src/memory/quarantine_repo.py
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict

DB_PATH = str(Path(__file__).resolve().parent.parent.parent / "data" / "kitty.db")

def _get_conn():
    return sqlite3.connect(DB_PATH)

def init_quarantine_db(conn=None):
    close = False
    if conn is None:
        conn = _get_conn()
        close = True
    conn.execute("""
        CREATE TABLE IF NOT EXISTS quarantine_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            candidate_data TEXT NOT NULL,
            source_message TEXT,
            confidence_score REAL DEFAULT 0.0,
            item_type TEXT CHECK(item_type IN ('memory','contradiction','action')) NOT NULL DEFAULT 'memory',
            status TEXT CHECK(status IN ('pending','approved','rejected')) NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.commit()
    if close:
        conn.close()

def add_quarantine_item(candidate_data: str, source_message: Optional[str] = None, 
                        confidence_score: float = 0.0, item_type: str = 'memory', conn=None) -> int:
    close = False
    if conn is None:
        conn = _get_conn()
        close = True
    cur = conn.execute(
        "INSERT INTO quarantine_queue (candidate_data, source_message, confidence_score, item_type, created_at) VALUES (?, ?, ?, ?, ?)",
        (candidate_data, source_message, confidence_score, item_type, datetime.now().isoformat())
    )
    conn.commit()
    tid = cur.lastrowid
    if close:
        conn.close()
    return tid

def get_pending_items(conn=None) -> List[Dict]:
    close = False
    if conn is None:
        conn = _get_conn()
        close = True
    rows = conn.execute("SELECT id, candidate_data, source_message, confidence_score, item_type, status, created_at FROM quarantine_queue WHERE status = 'pending' ORDER BY id DESC").fetchall()
    result = [{"id": r[0], "candidate_data": r[1], "source_message": r[2], 
               "confidence_score": r[3], "item_type": r[4], "status": r[5], "created_at": r[6]} for r in rows]
    if close:
        conn.close()
    return result

def update_item_status(item_id: int, status: str, conn=None) -> bool:
    close = False
    if conn is None:
        conn = _get_conn()
        close = True
    conn.execute("UPDATE quarantine_queue SET status = ? WHERE id = ?", (status, item_id))
    conn.commit()
    if close:
        conn.close()
    return True
