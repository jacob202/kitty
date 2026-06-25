"""Background Task Runner — queue and execute long-running work.

Task types:
- research:    Deep research with web search + synthesis
- ingest:      Document ingestion into knowledge base
- build:       Code generation and testing
- cleanup:     Data maintenance (prune old traces, compact indexes)
- dream:       Overnight batch (patterns, summaries, queue processing)

Public API:
  create(goal, task_type, **opts) -> task_id
  get(task_id) -> dict
  list_tasks(status_filter, limit) -> list[dict]
  get_output(task_id) -> str
  cancel(task_id) -> bool
"""

from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
import time
import uuid
from typing import Any, Optional

from gateway.paths import TASK_DB, TASK_OUTPUT_DIR

logger = logging.getLogger("kitty.task_runner")

VALID_TYPES = frozenset({"research", "ingest", "build", "cleanup", "dream", "wisdom"})
VALID_STATUSES = frozenset({"queued", "running", "completed", "failed", "cancelled"})


def init_db() -> None:
    TASK_DB.parent.mkdir(parents=True, exist_ok=True)
    TASK_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(TASK_DB) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                goal TEXT NOT NULL,
                task_type TEXT NOT NULL,
                status TEXT DEFAULT 'queued',
                created_at REAL,
                started_at REAL,
                completed_at REAL,
                progress TEXT DEFAULT '',
                error TEXT DEFAULT '',
                metadata TEXT DEFAULT '{}'
            )
        """)
        conn.commit()


def create(
    goal: str,
    task_type: str = "research",
    *,
    model: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
    run_immediately: bool = True,
) -> str:
    """Create a background task. Returns task_id."""
    if task_type not in VALID_TYPES:
        raise ValueError(
            f"Unknown task type: {task_type}. Valid: {sorted(VALID_TYPES)}"
        )

    init_db()
    task_id = str(uuid.uuid4())[:8]
    now = time.time()

    with sqlite3.connect(TASK_DB) as conn:
        conn.execute(
            "INSERT INTO tasks (id, goal, task_type, status, created_at, metadata) VALUES (?, ?, ?, ?, ?, ?)",
            (task_id, goal, task_type, "queued", now, json.dumps(metadata or {})),
        )
        conn.commit()

    logger.info("Task created: %s type=%s goal=%s", task_id, task_type, goal[:80])

    if run_immediately:
        asyncio.create_task(_execute(task_id))

    return task_id


def get(task_id: str) -> dict[str, Any]:
    """Get task details by ID."""
    init_db()
    with sqlite3.connect(TASK_DB) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if not row:
        return {"id": task_id, "status": "not_found"}
    return _row_to_dict(row)


def list_tasks(status: Optional[str] = None, limit: int = 20) -> list[dict[str, Any]]:
    """List tasks, newest first. Optional status filter."""
    init_db()
    with sqlite3.connect(TASK_DB) as conn:
        conn.row_factory = sqlite3.Row
        if status and status in VALID_STATUSES:
            rows = conn.execute(
                "SELECT * FROM tasks WHERE status = ? ORDER BY created_at DESC LIMIT ?",
                (status, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM tasks ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_output(task_id: str) -> str:
    """Get the full output text from a completed task."""
    output_file = TASK_OUTPUT_DIR / f"{task_id}.txt"
    if output_file.exists():
        return output_file.read_text()
    return ""


def cancel(task_id: str) -> bool:
    """Cancel a queued or running task."""
    init_db()
    with sqlite3.connect(TASK_DB) as conn:
        row = conn.execute(
            "SELECT status FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
        if not row:
            return False
        if row[0] not in ("queued", "running"):
            return False
        conn.execute(
            "UPDATE tasks SET status = 'cancelled', completed_at = ? WHERE id = ?",
            (time.time(), task_id),
        )
        conn.commit()
    logger.info("Task %s cancelled", task_id)
    return True


# --- Internal Execution ---


async def _execute(task_id: str) -> None:
    """Execute a task in the background."""
    task = get(task_id)
    if task["status"] != "queued":
        return

    _update(task_id, status="running", started_at=time.time())
    task_type = task["task_type"]
    goal = task["goal"]

    try:
        if task_type == "research":
            output = await _run_research(goal, task_id)
        elif task_type == "ingest":
            output = await _run_ingest(goal, task_id)
        elif task_type == "build":
            output = await _run_build(goal, task_id)
        elif task_type == "cleanup":
            output = await _run_cleanup(goal, task_id)
        elif task_type == "dream":
            output = await _run_dream(goal, task_id)
        elif task_type == "wisdom":
            output = await _run_wisdom(goal, task_id)
        else:
            output = f"Unknown task type: {task_type}"

        _save_output(task_id, output)
        _update(task_id, status="completed", completed_at=time.time())
        logger.info("Task %s completed", task_id)

    except asyncio.CancelledError:
        _update(task_id, status="cancelled", completed_at=time.time())
        logger.info("Task %s cancelled during execution", task_id)
    except Exception as e:
        logger.exception("Task %s failed", task_id)
        _update(task_id, status="failed", error=str(e)[:500], completed_at=time.time())


async def _run_research(goal: str, task_id: str) -> str:
    """Research task: use an explorer agent to investigate and report."""
    _update(task_id, progress="Running explorer agent...")
    from gateway.agent_runner import await_completion, spawn
    from gateway.agent_runner import get_output as agent_output

    session_id = await spawn(goal, agent_type="researcher", max_iterations=4)
    _update(task_id, progress=f"Agent spawned (session {session_id}), running...")

    await await_completion(
        session_id,
        on_poll=lambda status: _update(
            task_id, progress=f"Iteration {status.get('iterations', 0)}..."
        ),
    )
    return agent_output(session_id)


async def _run_ingest(goal: str, task_id: str) -> str:
    """Ingest task: queue documents for knowledge base ingestion."""
    _update(task_id, progress="Queueing ingestion...")
    from gateway.ingestion_queue import enqueue

    try:
        # goal is a file path or directory path to ingest
        enqueue(goal)
        return f"Ingestion queued for: {goal}"
    except Exception as e:
        return f"Ingestion failed: {e}"


async def _run_build(goal: str, task_id: str) -> str:
    """Build task: use a coder agent to generate code."""
    _update(task_id, progress="Running coder agent...")
    from gateway.agent_runner import await_completion, spawn
    from gateway.agent_runner import get_output as agent_output

    session_id = await spawn(goal, agent_type="coder", max_iterations=5)
    _update(task_id, progress=f"Coder agent running (session {session_id})...")

    await await_completion(
        session_id,
        on_poll=lambda status: _update(
            task_id, progress=f"Building... iteration {status.get('iterations', 0)}"
        ),
    )
    return agent_output(session_id)


async def _run_cleanup(goal: str, task_id: str) -> str:
    """Cleanup task: maintenance operations."""
    _update(task_id, progress="Running cleanup...")
    results = []
    # Compact old traces (keep last 30 days)
    try:
        from gateway.paths import LOG_FILE

        if LOG_FILE.exists():
            cutoff = time.time() - 30 * 86400
            lines = LOG_FILE.read_text().splitlines()
            kept = [l for l in lines if _line_after_cutoff(l, cutoff)]
            LOG_FILE.write_text("\n".join(kept) + "\n")
            results.append(f"Traces compacted: {len(lines)} -> {len(kept)} lines")
    except Exception as e:
        results.append(f"Trace cleanup failed: {e}")

    return "\n".join(results) if results else "No cleanup needed."


async def _run_dream(goal: str, task_id: str) -> str:
    """Dream task: overnight batch processing."""
    _update(task_id, progress="Dreaming...")
    results = []

    # Memory consolidation (summarize traces → long-term memory)
    try:
        from gateway.memory_consolidation import nightly_dream

        summary = await asyncio.to_thread(nightly_dream)
        results.append(summary)
    except Exception as e:
        results.append(f"Memory consolidation failed: {e}")

    # Run queued ingestions
    try:
        from gateway.ingestion_queue import process_queue

        count = process_queue()
        results.append(f"Ingestion queue: {count} items processed")
    except Exception as e:
        results.append(f"Ingestion queue failed: {e}")

    return "\n".join(results) if results else "Dream complete — nothing to do."


async def _run_wisdom(goal: str, task_id: str) -> str:
    """Wisdom task: run the lifted extract-wisdom skill over content (text or URL)."""
    _update(task_id, progress="Extracting wisdom...")
    from gateway import llm_client, skill_registry

    skill = skill_registry.get("extract-wisdom")
    system = (
        skill["content"]
        if skill
        else "Extract the most valuable, surprising, and actionable wisdom from the content."
    )
    try:
        return await asyncio.to_thread(
            llm_client.chat,
            llm_client.route_model("analyze extract wisdom"),
            [
                {"role": "system", "content": system},
                {"role": "user", "content": goal},
            ],
            1500,
            0.4,
        )
    except Exception as e:
        return f"Wisdom extraction failed: {e}"


# --- Helpers ---


def _update(task_id: str, **fields) -> None:
    """Update task fields in the database."""
    init_db()
    sets = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [task_id]
    with sqlite3.connect(TASK_DB) as conn:
        conn.execute(f"UPDATE tasks SET {sets} WHERE id = ?", values)
        conn.commit()


def _save_output(task_id: str, text: str) -> None:
    TASK_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (TASK_OUTPUT_DIR / f"{task_id}.txt").write_text(text)


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    d = dict(row)
    try:
        d["metadata"] = json.loads(d.get("metadata", "{}"))
    except (json.JSONDecodeError, TypeError):
        d["metadata"] = {}
    return d


def _line_after_cutoff(line: str, cutoff: float) -> bool:
    try:
        entry = json.loads(line)
        return entry.get("timestamp", 0) >= cutoff
    except json.JSONDecodeError:
        return True  # keep unparseable lines
