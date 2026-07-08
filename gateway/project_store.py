"""Project registry — CRUD for the projects table (P6, docs/packets/021).

Registry only: names, paths, status, and the fields project_resume's
refresh()/resume() compose and render. No git/memory/signal composition
lives here — see gateway/project_resume.py.

The kitty repo itself is seeded as project #1 on first init, the same
idempotent-once pattern as todo_store's legacy import: dogfoods the loop
instantly since kitty's own git/journal/signals are already local.

Public API:
  create(name, kind, paths=None, links=None) -> dict
  get(project_id) -> dict | None
  list_projects(status=None) -> list[dict]
  update_fields(project_id, **fields) -> dict
  touch(project_id) -> None
"""
from __future__ import annotations

import json
import sqlite3
import time
from typing import Any

from gateway import db as kitty_db
from gateway.paths import KITTY_DB_FILE, PROJECT_ROOT

PROJECTS_DB_FILE = KITTY_DB_FILE
KITTY_PROJECT_SEEDED_SETTING = "projects_kitty_seeded"
BENEFITS_PROJECT_SEEDED_SETTING = "projects_benefits_seeded"

_JSON_FIELDS = frozenset(
    {"paths_json", "open_questions_json", "next_actions_json", "delegable_json", "links_json"}
)
_UPDATABLE_FIELDS = frozenset(
    {
        "name",
        "kind",
        "status",
        "last_touched",
        "summary",
        "paths_json",
        "open_questions_json",
        "next_actions_json",
        "delegable_json",
        "links_json",
    }
)
_COLUMNS = (
    "id, created_at, name, kind, paths_json, status, last_touched, summary, "
    "open_questions_json, next_actions_json, delegable_json, links_json"
)


class ProjectError(RuntimeError):
    """Base for project-store errors."""


class ProjectNotFound(ProjectError):
    """No project row with that id (404-shaped)."""


def init_db() -> None:
    kitty_db.migrate(db_file=PROJECTS_DB_FILE)
    _seed_kitty_project_once()
    _seed_benefits_project_once()


def create(
    name: str,
    kind: str,
    paths: list[str] | None = None,
    links: list[Any] | None = None,
) -> dict[str, Any]:
    init_db()
    with kitty_db.connect(PROJECTS_DB_FILE) as conn:
        cursor = conn.execute(
            "INSERT INTO projects (name, kind, paths_json, links_json) VALUES (?, ?, ?, ?)",
            (name, kind, json.dumps(paths or []), json.dumps(links or [])),
        )
        conn.commit()
        project_id = cursor.lastrowid
    if project_id is None:
        raise ProjectError("insert did not return a row id")
    return _require(project_id)


def get(project_id: int) -> dict[str, Any] | None:
    init_db()
    with kitty_db.connect(PROJECTS_DB_FILE) as conn:
        row = conn.execute(f"SELECT {_COLUMNS} FROM projects WHERE id = ?", (project_id,)).fetchone()
    return _row_to_project(row) if row else None


def list_projects(status: str | None = None) -> list[dict[str, Any]]:
    init_db()
    with kitty_db.connect(PROJECTS_DB_FILE) as conn:
        if status is None:
            rows = conn.execute(f"SELECT {_COLUMNS} FROM projects ORDER BY id ASC").fetchall()
        else:
            rows = conn.execute(
                f"SELECT {_COLUMNS} FROM projects WHERE status = ? ORDER BY id ASC",
                (status,),
            ).fetchall()
    return [_row_to_project(r) for r in rows]


def update_fields(project_id: int, **fields: Any) -> dict[str, Any]:
    """Update one or more columns. JSON-shaped fields accept Python lists/dicts."""
    _require(project_id)
    set_clauses: list[str] = []
    values: list[Any] = []
    for key, value in fields.items():
        if key not in _UPDATABLE_FIELDS:
            raise ProjectError(f"cannot update field {key!r}")
        if key in _JSON_FIELDS:
            value = json.dumps(value)
        set_clauses.append(f"{key} = ?")
        values.append(value)
    if not set_clauses:
        return _require(project_id)
    values.append(project_id)
    with kitty_db.connect(PROJECTS_DB_FILE) as conn:
        conn.execute(f"UPDATE projects SET {', '.join(set_clauses)} WHERE id = ?", values)
        conn.commit()
    return _require(project_id)


def touch(project_id: int) -> None:
    """Bump last_touched to now."""
    update_fields(project_id, last_touched=time.time())


def delete(project_id: int) -> None:
    """Delete a project and its associated data (like next_steps)."""
    init_db()
    with kitty_db.connect(PROJECTS_DB_FILE) as conn:
        conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
        conn.execute("DELETE FROM next_steps WHERE project_id = ?", (project_id,))
        conn.commit()


def _require(project_id: int) -> dict[str, Any]:
    project = get(project_id)
    if project is None:
        raise ProjectNotFound(f"no project with id {project_id}")
    return project


def _row_to_project(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "created_at": row["created_at"],
        "name": row["name"],
        "kind": row["kind"],
        "paths": json.loads(row["paths_json"]),
        "status": row["status"],
        "last_touched": row["last_touched"],
        "summary": row["summary"],
        "open_questions": json.loads(row["open_questions_json"]),
        "next_actions": json.loads(row["next_actions_json"]),
        "delegable": json.loads(row["delegable_json"]),
        "links": json.loads(row["links_json"]),
    }


def _seed_kitty_project_once() -> None:
    """Register the kitty repo itself as project #1. Idempotent, once ever."""
    with kitty_db.connect(PROJECTS_DB_FILE) as conn:
        seeded = conn.execute(
            "SELECT value FROM app_settings WHERE key = ?",
            (KITTY_PROJECT_SEEDED_SETTING,),
        ).fetchone()
        if seeded:
            return
        conn.execute(
            "INSERT INTO projects (name, kind, paths_json, links_json) VALUES (?, ?, ?, ?)",
            ("kitty", "code", json.dumps([str(PROJECT_ROOT)]), json.dumps([])),
        )
        conn.execute(
            "INSERT OR REPLACE INTO app_settings (key, value, updated_at) "
            "VALUES (?, ?, CURRENT_TIMESTAMP)",
            (KITTY_PROJECT_SEEDED_SETTING, "1"),
        )
        conn.commit()


def _seed_benefits_project_once() -> None:
    """Register the benefits-admin project as project #2. Idempotent, once ever (P7)."""
    with kitty_db.connect(PROJECTS_DB_FILE) as conn:
        seeded = conn.execute(
            "SELECT value FROM app_settings WHERE key = ?",
            (BENEFITS_PROJECT_SEEDED_SETTING,),
        ).fetchone()
        if seeded:
            return
        conn.execute(
            "INSERT INTO projects (name, kind, paths_json, links_json) VALUES (?, ?, ?, ?)",
            ("benefits-admin", "admin", json.dumps([]), json.dumps([])),
        )
        conn.execute(
            "INSERT OR REPLACE INTO app_settings (key, value, updated_at) "
            "VALUES (?, ?, CURRENT_TIMESTAMP)",
            (BENEFITS_PROJECT_SEEDED_SETTING, "1"),
        )
        conn.commit()
