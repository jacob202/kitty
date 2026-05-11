"""SQLite-backed ingestion queue for Kitty. 

Moves book processing from a fragile synchronous loop to a robust background worker
that can handle crashes, restarts, and disk-full scenarios gracefully.
"""
from __future__ import annotations
import sqlite3
import time
import logging
from pathlib import Path
from typing import Optional, List, Dict

from gateway.paths import DATA_DIR
from gateway.knowledge import ingest_file

logger = logging.getLogger("kitty.ingestion_queue")
QUEUE_DB = DATA_DIR / "ingestion_queue.db"

def init_db():
    """Initialize the queue database."""
    with sqlite3.connect(QUEUE_DB) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ingestion_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT UNIQUE,
                doc_type TEXT,
                sensitivity TEXT,
                status TEXT DEFAULT 'pending', -- pending, processing, completed, failed
                error_message TEXT,
                attempts INTEGER DEFAULT 0,
                created_at REAL,
                updated_at REAL
            )
        """)
        conn.commit()

def enqueue_file(file_path: str | Path, doc_type: Optional[str] = None, sensitivity: str = "low"):
    """Add a file to the ingestion queue if not already present."""
    path = str(Path(file_path).expanduser().resolve())
    now = time.time()
    try:
        with sqlite3.connect(QUEUE_DB) as conn:
            conn.execute("""
                INSERT INTO ingestion_queue (file_path, doc_type, sensitivity, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(file_path) DO UPDATE SET updated_at = ?
            """, (path, doc_type, sensitivity, now, now, now))
            conn.commit()
    except Exception as e:
        logger.error("Failed to enqueue %s: %s", path, e)

def get_next_task() -> Optional[Dict]:
    """Fetch the next pending or retryable task."""
    with sqlite3.connect(QUEUE_DB) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("""
            SELECT * FROM ingestion_queue 
            WHERE status IN ('pending', 'failed') AND attempts < 3
            ORDER BY created_at ASC LIMIT 1
        """).fetchone()
        if row:
            return dict(row)
    return None

def update_task_status(task_id: int, status: str, error: Optional[str] = None):
    """Update the status of a task."""
    now = time.time()
    with sqlite3.connect(QUEUE_DB) as conn:
        if status == 'processing':
            conn.execute("""
                UPDATE ingestion_queue 
                SET status = ?, attempts = attempts + 1, updated_at = ? 
                WHERE id = ?
            """, (status, now, task_id))
        else:
            conn.execute("""
                UPDATE ingestion_queue 
                SET status = ?, error_message = ?, updated_at = ? 
                WHERE id = ?
            """, (status, error, now, task_id))
        conn.commit()

def process_queue():
    """Worker loop to process the queue."""
    init_db()
    logger.info("Ingestion worker started.")
    
    while True:
        task = get_next_task()
        if not task:
            time.sleep(5) # Wait for new tasks
            continue
            
        task_id = task['id']
        file_path = task['file_path']
        
        logger.info("Processing task %d: %s", task_id, file_path)
        update_task_status(task_id, 'processing')
        
        try:
            # Call the unified ingestion engine
            num_chunks = ingest_file(
                file_path=file_path,
                doc_type=task['doc_type'],
                sensitivity=task['sensitivity']
            )
            update_task_status(task_id, 'completed')
            logger.info("Completed task %d: %s (%d chunks)", task_id, file_path, num_chunks)
        except Exception as e:
            logger.error("Task %d failed: %s", task_id, e)
            update_task_status(task_id, 'failed', str(e))
            time.sleep(2) # Backoff on error

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    process_queue()
