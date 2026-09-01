"""Durable execution truth for deep-research runs."""
from __future__ import annotations

import json
import sqlite3
import time
import uuid
from typing import Any

from gateway import db as kitty_db
from gateway.paths import KITTY_DB_FILE

DB_FILE = KITTY_DB_FILE
PROCESS_STARTED_AT = time.time()
_ALLOWED_STAGES = frozenset({'queued', 'searching', 'reading', 'synthesizing', 'saving', 'completed', 'failed', 'interrupted'})
_TERMINAL = frozenset({'completed', 'failed', 'interrupted'})


class ResearchRunError(RuntimeError):
    pass


class ResearchRunNotFound(ResearchRunError):
    pass


def init_db() -> None:
    kitty_db.migrate(db_file=DB_FILE)


def _row(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    result = dict(row)
    try:
        result['sources'] = json.loads(result.pop('sources_json') or '[]')
    except json.JSONDecodeError:
        result['sources'] = []
    return result


def begin_run(*, topic: str, project_id: int | None = None, created_at: float | None = None) -> dict[str, Any]:
    if not topic.strip():
        raise ResearchRunError('topic must not be empty')
    if project_id is not None and (isinstance(project_id, bool) or project_id <= 0):
        raise ResearchRunError('project_id must be a positive integer')
    init_db()
    now = time.time() if created_at is None else float(created_at)
    run_id = f"rrun_{uuid.uuid4().hex}"
    with kitty_db.connect(DB_FILE) as conn:
        conn.execute(
            "INSERT INTO research_runs (id, topic, project_id, status, stage, sources_json, created_at, updated_at) "
            "VALUES (?, ?, ?, 'running', 'queued', '[]', ?, ?)",
            (run_id, topic.strip(), project_id, now, now),
        )
        conn.commit()
    current = get_run(run_id)
    if current is None:
        raise ResearchRunError('research run insert did not persist')
    return current


def get_run(run_id: str) -> dict[str, Any] | None:
    init_db()
    with kitty_db.connect(DB_FILE) as conn:
        row = conn.execute('SELECT * FROM research_runs WHERE id = ?', (run_id,)).fetchone()
    return _row(row)


def list_runs(*, limit: int = 20, project_id: int | None = None) -> list[dict[str, Any]]:
    init_db()
    bounded = max(1, min(int(limit), 100))
    with kitty_db.connect(DB_FILE) as conn:
        if project_id is None:
            rows = conn.execute('SELECT * FROM research_runs ORDER BY created_at DESC LIMIT ?', (bounded,)).fetchall()
        else:
            rows = conn.execute(
                'SELECT * FROM research_runs WHERE project_id = ? ORDER BY created_at DESC LIMIT ?',
                (project_id, bounded),
            ).fetchall()
    result: list[dict[str, Any]] = []
    for row in rows:
        item = _row(row)
        if item is not None:
            result.append(item)
    return result


def update_stage(run_id: str, *, stage: str, sources: list[str] | None = None, updated_at: float | None = None) -> dict[str, Any]:
    if stage not in _ALLOWED_STAGES - _TERMINAL:
        raise ResearchRunError(f'invalid running stage {stage!r}')
    now = time.time() if updated_at is None else float(updated_at)
    sources_json = json.dumps(list(dict.fromkeys(sources))) if sources is not None else None
    init_db()
    with kitty_db.connect(DB_FILE) as conn:
        cursor = conn.execute(
            "UPDATE research_runs SET stage = ?, updated_at = ?, sources_json = COALESCE(?, sources_json) "
            "WHERE id = ? AND status = 'running'",
            (stage, now, sources_json, run_id),
        )
        conn.commit()
        if cursor.rowcount != 1:
            if get_run(run_id) is None:
                raise ResearchRunNotFound(run_id)
            raise ResearchRunError(f'research run {run_id} is not running')
    return get_run(run_id) or (_ for _ in ()).throw(ResearchRunNotFound(run_id))


def complete_run(run_id: str, *, summary: str, artifact_id: str, sources: list[str], completed_at: float | None = None) -> dict[str, Any]:
    now = time.time() if completed_at is None else float(completed_at)
    init_db()
    with kitty_db.connect(DB_FILE) as conn:
        cursor = conn.execute(
            "UPDATE research_runs SET status = 'completed', stage = 'completed', summary = ?, artifact_id = ?, "
            "sources_json = ?, error = NULL, updated_at = ?, completed_at = ? WHERE id = ? AND status = 'running'",
            (summary, artifact_id, json.dumps(list(dict.fromkeys(sources))), now, now, run_id),
        )
        conn.commit()
        if cursor.rowcount != 1:
            raise ResearchRunError(f'research run {run_id} is not running')
    return get_run(run_id) or (_ for _ in ()).throw(ResearchRunNotFound(run_id))


def fail_run(run_id: str, *, error: str, status: str = 'failed', completed_at: float | None = None) -> dict[str, Any]:
    if status not in {'failed', 'interrupted'}:
        raise ResearchRunError(f'invalid failure status {status!r}')
    now = time.time() if completed_at is None else float(completed_at)
    init_db()
    with kitty_db.connect(DB_FILE) as conn:
        cursor = conn.execute(
            "UPDATE research_runs SET status = ?, stage = ?, error = ?, updated_at = ?, completed_at = ? "
            "WHERE id = ? AND status = 'running'",
            (status, status, str(error)[:2000], now, now, run_id),
        )
        conn.commit()
        if cursor.rowcount != 1:
            raise ResearchRunError(f'research run {run_id} is not running')
    return get_run(run_id) or (_ for _ in ()).throw(ResearchRunNotFound(run_id))


def reconcile_interrupted(*, now: float | None = None) -> int:
    init_db()
    timestamp = time.time() if now is None else float(now)
    with kitty_db.connect(DB_FILE) as conn:
        cursor = conn.execute(
            "UPDATE research_runs SET status = 'interrupted', stage = 'interrupted', "
            "error = 'gateway restarted before research completed', updated_at = ?, completed_at = ? "
            "WHERE status = 'running' AND created_at < ?",
            (timestamp, timestamp, PROCESS_STARTED_AT),
        )
        conn.commit()
        return int(cursor.rowcount)
