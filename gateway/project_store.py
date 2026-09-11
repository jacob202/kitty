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
from pathlib import Path
from typing import Any

from gateway import db as kitty_db
from gateway.paths import KITTY_DB_FILE, PROJECT_ROOT

PROJECTS_DB_FILE = KITTY_DB_FILE
KITTY_PROJECT_SEEDED_SETTING = "projects_kitty_seeded"
BENEFITS_PROJECT_SEEDED_SETTING = "projects_benefits_seeded"

_JSON_FIELDS = frozenset(
    {"paths_json", "open_questions_json", "next_actions_json", "delegable_json", "links_json"}
)
# Only work that can still be done is a "next action".
ACTIONABLE_TODO_STATUSES = frozenset({"pending", "in_progress"})

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
    "open_questions_json, next_actions_json, delegable_json, links_json, "
    "selected_todo_id"
)


class ProjectError(RuntimeError):
    """Base for project-store errors."""


class ProjectNotFound(ProjectError):
    """No project row with that id (404-shaped)."""


class ProjectDeletionDisabledError(ProjectError):
    """Hard deletion is unavailable until project relationship integrity is complete."""


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
    """Refuse hard deletion; projects with history must be archived instead.

    Several durable owners already link by ``project_id`` without database-level
    foreign keys (notably chat lifecycle and Artifacts). A pre-delete reference
    scan cannot close the race with a concurrent writer. Until those relationships
    have transactional/FK integrity, destructive deletion is not a truthful product
    operation. ``status='archived'`` is the existing reversible lifecycle.
    """
    init_db()
    _require(project_id)
    raise ProjectDeletionDisabledError(
        f"cannot hard-delete project {project_id}; archive it by setting status='archived'"
    )


def restore(items: list[dict[str, Any]]) -> int:
    """Replace Projects with snapshot state.

    Snapshot restore has the opposite contract to ``update_fields``: rows
    omitted from the snapshot are absent afterwards. ``delete()``'s archive-only
    policy governs user-initiated deletion, not wholesale snapshot replacement,
    which is the same precedent ``todo_store.restore`` sets for Todos. Todos are
    restored immediately after this in the same ``storage_sync`` pass, so a
    ``selected_todo_id`` that is dangling only because its todo has not landed
    yet is reconciled there rather than rejected here.
    """
    init_db()
    rows, seen_ids = _restore_rows(items)

    with kitty_db.connect(PROJECTS_DB_FILE) as conn:
        # Update snapshot projects in place so foreign-key dependents keep the
        # same parent row. Only projects omitted from the snapshot are deleted.
        # If an omitted project is still referenced, SQLite rejects that delete
        # and the transaction rolls back rather than corrupting dependent state.
        conn.execute("BEGIN IMMEDIATE")
        try:
            _write_restore(conn, rows, seen_ids)
        except sqlite3.IntegrityError as exc:
            conn.rollback()
            raise _omitted_referenced_error() from exc
        conn.commit()
    return len(rows)


def _write_restore(
    conn: sqlite3.Connection, rows: list[tuple[Any, ...]], seen_ids: set[int]
) -> None:
    """Upsert the snapshot rows and drop only what the snapshot omits.

    Caller owns the transaction. Shared with ``validate_restore`` so the prove
    step exercises exactly the statements the real restore runs.
    """
    conn.executemany(
        "INSERT INTO projects (id, created_at, name, kind, paths_json, status, "
        "last_touched, summary, open_questions_json, next_actions_json, delegable_json, "
        "links_json, selected_todo_id) "
        "VALUES (?, COALESCE(?, CURRENT_TIMESTAMP), ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(id) DO UPDATE SET "
        "created_at=excluded.created_at, name=excluded.name, kind=excluded.kind, "
        "paths_json=excluded.paths_json, status=excluded.status, "
        "last_touched=excluded.last_touched, summary=excluded.summary, "
        "open_questions_json=excluded.open_questions_json, "
        "next_actions_json=excluded.next_actions_json, delegable_json=excluded.delegable_json, "
        "links_json=excluded.links_json, selected_todo_id=excluded.selected_todo_id",
        rows,
    )
    _delete_omitted_projects(conn, seen_ids)


def _restore_rows(items: list[dict[str, Any]]) -> tuple[list[tuple[Any, ...]], set[int]]:
    """Validate a projects payload and shape it for restore, or raise."""
    if not isinstance(items, list):
        raise ProjectError(f"projects payload must be a list, got {type(items).__name__}")

    rows: list[tuple[Any, ...]] = []
    seen_ids: set[int] = set()
    for item in items:
        if not isinstance(item, dict):
            raise ProjectError(f"project record must be a dict, got {type(item).__name__}")
        raw_id = item.get("id")
        if not isinstance(raw_id, int) or isinstance(raw_id, bool):
            raise ProjectError("project records must carry an integer id to restore")
        if raw_id in seen_ids:
            raise ProjectError(f"duplicate project id {raw_id} in snapshot")
        seen_ids.add(raw_id)
        # A malformed owner must fail loud. Writing it raw lets Todo restore
        # reconcile the pointer away and report a successful import, which
        # silently drops the project's explicitly chosen action.
        raw_selected = item.get("selected_todo_id")
        if raw_selected is not None and (
            not isinstance(raw_selected, int) or isinstance(raw_selected, bool)
        ):
            raise ProjectError("project selected_todo_id must be an integer or null")
        created_at = item.get("created_at")
        rows.append(
            (
                raw_id,
                created_at if isinstance(created_at, str) and created_at else None,
                str(item.get("name", "")),
                str(item.get("kind", "")),
                json.dumps(item.get("paths") or []),
                str(item.get("status") or "active"),
                item.get("last_touched"),
                str(item.get("summary") or ""),
                json.dumps(item.get("open_questions") or []),
                json.dumps(item.get("next_actions") or []),
                json.dumps(item.get("delegable") or []),
                json.dumps(item.get("links") or []),
                raw_selected,
            )
        )
    return rows, seen_ids


def _delete_omitted_projects(conn: sqlite3.Connection, snapshot_ids: set[int]) -> None:
    """Delete only projects absent from the snapshot. Raises on a live reference."""
    existing_ids = {row["id"] for row in conn.execute("SELECT id FROM projects")}
    stale_ids = sorted(existing_ids - snapshot_ids)
    if not stale_ids:
        return
    placeholders = ",".join("?" for _ in stale_ids)
    conn.execute(f"DELETE FROM projects WHERE id IN ({placeholders})", stale_ids)


def _omitted_referenced_error() -> ProjectError:
    return ProjectError(
        "cannot remove snapshot-omitted projects while they are still referenced"
    )


def validate_restore(items: list[dict[str, Any]]) -> None:
    """Prove ``restore`` can replace Projects, changing nothing.

    ``storage_sync`` writes other stores before Projects, so a payload that only
    fails on a foreign-key dependent — or on a value SQLite cannot bind — would
    leave those earlier stores committed against a rejected snapshot. This runs
    the real upsert and omit-delete in a transaction that is always rolled back,
    so callers can fail before any store is written while nothing here persists.
    """
    init_db()
    rows, seen_ids = _restore_rows(items)
    with kitty_db.connect(PROJECTS_DB_FILE) as conn:
        conn.execute("BEGIN IMMEDIATE")
        try:
            _write_restore(conn, rows, seen_ids)
        except sqlite3.IntegrityError as exc:
            raise _omitted_referenced_error() from exc
        finally:
            conn.rollback()


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
        "selected_todo_id": row["selected_todo_id"],
    }


def select_todo(project_id: int, todo_id: int) -> dict[str, Any]:
    """Record the one action the user explicitly chose for this project.

    Explicit choice outranks anything generated. `next_actions_json` and
    `project_next_steps` are both replaceable suggestion state; this is not,
    and regenerating either must leave it alone.
    """
    if not isinstance(todo_id, int) or isinstance(todo_id, bool):
        raise ProjectError(f"todo_id must be int, got {type(todo_id).__name__}")
    from gateway import todo_store

    if Path(todo_store.TODO_DB_FILE).resolve() != Path(PROJECTS_DB_FILE).resolve():
        raise ProjectError(
            "cannot select a todo while the todo and project stores are separate databases"
        )
    init_db()
    todo_store.init_db()
    with kitty_db.connect(PROJECTS_DB_FILE) as conn:
        # Lock before validating either row. A validation performed before the
        # write transaction can become false while this request waits for a
        # concurrent selection or model refresh.
        conn.execute("BEGIN IMMEDIATE")
        project = conn.execute(
            "SELECT id FROM projects WHERE id = ?", (project_id,)
        ).fetchone()
        if project is None:
            raise ProjectNotFound(f"no project with id {project_id}")
        chosen = conn.execute(
            "SELECT id, status, project_id FROM todos WHERE id = ?", (todo_id,)
        ).fetchone()
        if chosen is None:
            raise ProjectNotFound(f"no todo with id {todo_id}")
        if chosen["status"] not in ACTIONABLE_TODO_STATUSES:
            raise ProjectError(
                f"todo {todo_id} is {chosen['status']} and cannot be the next action"
            )
        owner = chosen["project_id"]
        if owner is not None and owner != project_id:
            raise ProjectError(f"todo {todo_id} belongs to project {owner}, not {project_id}")
        if owner is None:
            # Adoption and selection must land together. Committing ownership
            # first through a separate connection leaves a todo adopted with no
            # selection if the second write fails.
            claimed = conn.execute(
                "UPDATE todos SET project_id = ?, updated_at = ? "
                "WHERE id = ? AND project_id IS NULL",
                (project_id, time.time(), todo_id),
            )
            if claimed.rowcount != 1:
                raise ProjectError(f"todo {todo_id} changed ownership while it was selected")
        conn.execute(
            "UPDATE projects SET selected_todo_id = ? WHERE id = ?", (todo_id, project_id)
        )
        conn.commit()
    return _require(project_id)


def clear_selected_todo(project_id: int) -> dict[str, Any]:
    """Drop the explicit selection without touching the todo itself."""
    _require(project_id)
    with kitty_db.connect(PROJECTS_DB_FILE) as conn:
        conn.execute(
            "UPDATE projects SET selected_todo_id = NULL WHERE id = ?", (project_id,)
        )
        conn.commit()
    return _require(project_id)


def selected_todo(project_id: int) -> dict[str, Any] | None:
    """Return the chosen todo, repairing the pointer if that todo is gone.

    A selection pointing at a deleted todo would otherwise surface as a
    phantom next action. Rather than dangle, the pointer clears itself the
    first time anyone looks.
    """
    project = _require(project_id)
    todo_id = project.get("selected_todo_id")
    if todo_id is None:
        return None
    from gateway import todo_store

    if Path(todo_store.TODO_DB_FILE).resolve() != Path(PROJECTS_DB_FILE).resolve():
        raise ProjectError(
            "cannot read a selected todo while the todo and project stores are separate databases"
        )
    chosen = next((todo for todo in todo_store.get() if todo["id"] == todo_id), None)
    if chosen is None:
        _clear_selected_todo_if_current(project_id, todo_id)
        return None
    # The selection was valid when it was made; the todo can have moved or been
    # finished since. Both mean this project no longer has a chosen next action,
    # and returning one anyway would put another project's work — or work
    # already done — in front of the user as the thing to do next.
    # An existing selection must still be owned by *this* project. `owner is
    # None` is not good enough: /todos/{id}/project accepts null, so a selected
    # todo can be explicitly unassigned and would otherwise keep being returned
    # as this project's chosen action.
    if chosen.get("project_id") != project_id:
        _clear_selected_todo_if_current(project_id, todo_id)
        return None
    if chosen["status"] not in ACTIONABLE_TODO_STATUSES:
        _clear_selected_todo_if_current(project_id, todo_id)
        return None
    return chosen


def _clear_selected_todo_if_current(project_id: int, expected_todo_id: int) -> bool:
    """Repair one stale pointer without erasing a newer explicit choice."""
    with kitty_db.connect(PROJECTS_DB_FILE) as conn:
        cursor = conn.execute(
            "UPDATE projects SET selected_todo_id = NULL "
            "WHERE id = ? AND selected_todo_id = ?",
            (project_id, expected_todo_id),
        )
        conn.commit()
        return cursor.rowcount == 1


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
