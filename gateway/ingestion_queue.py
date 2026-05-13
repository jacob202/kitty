"""SQLite-backed ingestion queue for Kitty.

Moves document processing from a fragile synchronous loop to a robust background
worker that can handle crashes, restarts, disk-full scenarios, and cascading
failures gracefully.

Error Break Loop
================
The worker tracks errors in two dimensions:

1. Per-task errors  — a single file fails up to MAX_ATTEMPTS (3) times before
                      being marked permanently failed.
2. Global circuit   — if GLOBAL_ERROR_THRESHOLD (3) consecutive tasks fail
                      (regardless of file), the worker HALTs and writes a
                      sentinel file so an external watchdog or operator can
                      inspect before restart.

Backoff strategy:
  - Exponential backoff starting at BASE_DELAY, capped at MAX_DELAY.
  - Successful task resets the backoff counter.
  - On circuit-open, the worker stops entirely and logs a clear diagnostic.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import sqlite3
import time
from pathlib import Path
from typing import Optional, List, Dict, Tuple

from gateway.paths import DATA_DIR

logger = logging.getLogger("kitty.ingestion_queue")

QUEUE_DB = DATA_DIR / "ingestion_queue.db"

# --- Error-break / circuit-breaker configuration --------------------------------

MAX_ATTEMPTS = 3                          # per-file retry ceiling
GLOBAL_ERROR_THRESHOLD = 3                # consecutive task failures → halt
BASE_DELAY = 2.0                          # seconds, initial backoff
MAX_DELAY = 60.0                          # seconds, backoff ceiling
BACKOFF_MULTIPLIER = 2.0                  # exponential factor

HALT_SENTINEL = DATA_DIR / "ingestion_halted"  # presence of this file = paused

# --- Error classification ----------------------------------------------------

# Error prefixes used to classify failures for logging and diagnostics.
_ERROR_CATEGORIES: Dict[str, str] = {
    "OSError":        "filesystem / I/O",
    "IOError":        "filesystem / I/O",
    "PermissionError":"filesystem / permissions",
    "MemoryError":    "memory",
    "TimeoutError":   "timeout",
    "ConnectionError":"network",
    "ValueError":     "data / parsing",
    "KeyError":       "data / missing field",
    "TypeError":      "data / type mismatch",
    "RuntimeError":   "runtime",
}


def _classify_error(exc: BaseException) -> Tuple[str, str]:
    """Return (category, short_label) for an exception."""
    if isinstance(exc, sqlite3.Error):
        return "database", type(exc).__name__
    for cls_name, label in _ERROR_CATEGORIES.items():
        if cls_name in type(exc).__name__:
            return label, cls_name
    return "unknown", type(exc).__name__


# --- Database helpers ---------------------------------------------------------

def init_db() -> None:
    """Initialize the queue database."""
    with sqlite3.connect(str(QUEUE_DB)) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ingestion_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT UNIQUE,
                doc_type TEXT,
                sensitivity TEXT,
                status TEXT DEFAULT 'pending',
                error_message TEXT,
                attempts INTEGER DEFAULT 0,
                created_at REAL,
                updated_at REAL
            )
        """)
        columns = {row[1] for row in conn.execute("PRAGMA table_info(ingestion_queue)")}
        if "authority_score" not in columns:
            conn.execute("ALTER TABLE ingestion_queue ADD COLUMN authority_score INTEGER DEFAULT 0")
        if "source_brief" not in columns:
            conn.execute("ALTER TABLE ingestion_queue ADD COLUMN source_brief TEXT")
        conn.commit()


def clear_queue() -> int:
    """Delete every row in the ingestion queue. Returns how many rows were removed."""
    init_db()
    with sqlite3.connect(str(QUEUE_DB)) as conn:
        cur = conn.execute("SELECT COUNT(*) FROM ingestion_queue")
        n = int(cur.fetchone()[0])
        conn.execute("DELETE FROM ingestion_queue")
        conn.commit()
    logger.info("Cleared ingestion queue (%d rows removed).", n)
    return n


def enqueue_file(
    file_path: str | Path,
    doc_type: Optional[str] = None,
    sensitivity: str = "low",
) -> None:
    """Add a file to the ingestion queue if not already present."""
    path = str(Path(file_path).expanduser().resolve())
    now = time.time()
    try:
        with sqlite3.connect(str(QUEUE_DB)) as conn:
            conn.execute(
                """
                INSERT INTO ingestion_queue
                    (file_path, doc_type, sensitivity, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(file_path) DO UPDATE SET updated_at = ?
                """,
                (path, doc_type, sensitivity, now, now, now),
            )
            conn.commit()
    except sqlite3.Error as e:
        logger.error("Failed to enqueue %s: %s", path, e)


def get_next_task() -> Optional[Dict]:
    """Fetch the next pending or retryable task."""
    with sqlite3.connect(str(QUEUE_DB)) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            """
            SELECT * FROM ingestion_queue
            WHERE status IN ('pending', 'failed') AND attempts < ?
            ORDER BY COALESCE(authority_score, 0) DESC, created_at ASC
            LIMIT 1
            """,
            (MAX_ATTEMPTS,),
        ).fetchone()
        if row:
            return dict(row)
    return None


def update_task_status(
    task_id: int,
    status: str,
    error: Optional[str] = None,
) -> None:
    """Update the status of a task."""
    now = time.time()
    with sqlite3.connect(str(QUEUE_DB)) as conn:
        if status == "processing":
            conn.execute(
                """
                UPDATE ingestion_queue
                SET status = ?, attempts = attempts + 1, updated_at = ?
                WHERE id = ?
                """,
                (status, now, task_id),
            )
        else:
            conn.execute(
                """
                UPDATE ingestion_queue
                SET status = ?, error_message = ?, updated_at = ?
                WHERE id = ?
                """,
                (status, error, now, task_id),
            )
        conn.commit()


def get_error_summary() -> Dict:
    """Return a diagnostic dict with queue error statistics."""
    with sqlite3.connect(str(QUEUE_DB)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT status, COUNT(*) AS cnt FROM ingestion_queue GROUP BY status"
        ).fetchall()
        summary = {row["status"]: row["cnt"] for row in rows}
        failed = conn.execute(
            "SELECT error_message FROM ingestion_queue WHERE status = 'failed'"
        ).fetchall()
        error_samples = [r["error_message"] for r in failed if r["error_message"]]
        return {
            "queue_summary": summary,
            "error_samples": error_samples[:10],  # cap for readability
        }


# --- Halt / circuit-breaker helpers ------------------------------------------

def _write_halt_sentinel(error_summary: Dict) -> None:
    """Write a JSON sentinel file so watchdogs / operators see why we stopped."""
    HALT_SENTINEL.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "halted_at": time.time(),
        "reason": "global_error_threshold_reached",
        "errors": error_summary,
    }
    with open(HALT_SENTINEL, "w") as f:
        json.dump(payload, f, indent=2)
    logger.error("Halt sentinel written to %s", HALT_SENTINEL)


def _is_halted() -> bool:
    """Return True if a halt sentinel file exists on disk."""
    return HALT_SENTINEL.exists()


def clear_halt_flag() -> None:
    """Remove the halt sentinel to allow the worker to resume."""
    if HALT_SENTINEL.exists():
        HALT_SENTINEL.unlink()
        logger.info("Halt flag cleared — worker may resume.")
    else:
        logger.info("No halt flag present.")


# --- Backoff helper ----------------------------------------------------------

def _backoff(attempt: int) -> float:
    """Return sleep seconds for a given consecutive-failure attempt (1-indexed)."""
    delay = min(BASE_DELAY * (BACKOFF_MULTIPLIER ** (attempt - 1)), MAX_DELAY)
    logger.info("Backoff: %.1fs (attempt %d)", delay, attempt)
    return delay


# --- Main worker loop --------------------------------------------------------

async def process_queue() -> None:
    """Worker loop with error break / circuit-breaker logic.

    The loop exits cleanly when:
      - A global error threshold of consecutive task failures is hit (circuit
        opens).  A halt sentinel is written and the worker stops.
      - The queue is empty for an extended idle period (implicit via sleep).

    To resume after a halt, call ``clear_halt_flag()`` or delete the sentinel
    file, then restart the worker.
    """
    init_db()

    if _is_halted():
        logger.warning(
            "Halt sentinel detected. Worker is paused. "
            "Run `clear_halt_flag()` or remove %s to resume.",
            HALT_SENTINEL,
        )
        return

    logger.info("Ingestion worker started (error_threshold=%d).", GLOBAL_ERROR_THRESHOLD)

    global_error_count = 0      # consecutive failures across tasks
    backoff_until: float = 0.0  # monotonic time before next retry

    while True:
        # --- Idle polling ---------------------------------------------------
        now = time.monotonic()
        if now < backoff_until:
            await asyncio.sleep(backoff_until - now)

        task = get_next_task()
        if task is None:
            logger.info("Ingestion queue has no actionable tasks — worker exiting.")
            return

        task_id = task["id"]
        file_path = task["file_path"]

        logger.info("Processing task %d: %s", task_id, file_path)
        update_task_status(task_id, "processing")

        try:
            from gateway.knowledge import ingest_file

            result = await ingest_file(
                file_path=file_path,
                doc_type=task["doc_type"],
                sensitivity=task["sensitivity"],
            )
            update_task_status(task_id, "completed")
            logger.info(
                "Completed task %d: %s (%d chunks)",
                task_id,
                file_path,
                result.chunks_count,
            )
            # Success: reset global counter and backoff
            global_error_count = 0
            backoff_until = 0.0

        except Exception as e:
            category, label = _classify_error(e)
            logger.error(
                "Task %d failed [%s / %s]: %s",
                task_id,
                category,
                label,
                e,
                exc_info=True,
            )
            update_task_status(task_id, "failed", f"[{label}] {e}")
            global_error_count += 1

            # --- Circuit-breaker check --------------------------------------
            if global_error_count >= GLOBAL_ERROR_THRESHOLD:
                logger.error(
                    "ERROR BREAK: %d consecutive task failures reached. "
                    "Halting ingestion worker.",
                    global_error_count,
                )
                summary = get_error_summary()
                _write_halt_sentinel(summary)
                return  # clean exit — caller can restart or inspect

            # --- Exponential backoff ----------------------------------------
            delay = _backoff(global_error_count)
            backoff_until = time.monotonic() + delay

    # (unreachable — loop exits via return on halt or Ctrl-C)


# --- Entrypoint --------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
    )
    asyncio.run(process_queue())
