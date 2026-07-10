"""Persisted active-project scope for gateway requests."""

from __future__ import annotations

from typing import Any

from gateway import db as kitty_db
from gateway import project_store
from gateway.paths import KITTY_DB_FILE

ACTIVE_PROJECT_SETTING = "active_project_id"


class ProjectContextError(RuntimeError):
    """Raised when the persisted project scope is missing or corrupt."""


def _write_active_project_id(project_id: int) -> None:
    with kitty_db.connect(KITTY_DB_FILE) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO app_settings (key, value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            """,
            (ACTIVE_PROJECT_SETTING, str(project_id)),
        )
        conn.commit()


def _stored_project_id() -> int | None:
    with kitty_db.connect(KITTY_DB_FILE) as conn:
        row = conn.execute(
            "SELECT value FROM app_settings WHERE key = ?",
            (ACTIVE_PROJECT_SETTING,),
        ).fetchone()
    if row is None:
        return None
    raw = row["value"]
    try:
        project_id = int(raw)
    except (TypeError, ValueError) as exc:
        raise ProjectContextError(
            f"{ACTIVE_PROJECT_SETTING} contains invalid value {raw!r}"
        ) from exc
    if project_id <= 0:
        raise ProjectContextError(
            f"{ACTIVE_PROJECT_SETTING} must be positive, got {project_id}"
        )
    return project_id


def _project_result(project: dict[str, Any], source: str) -> dict[str, Any]:
    return {"project_id": project["id"], "project": project, "source": source}


def get_active_project() -> dict[str, Any]:
    """Return the persisted project, initializing the first active project once."""
    project_store.init_db()
    stored_id = _stored_project_id()
    if stored_id is not None:
        project = project_store.get(stored_id)
        if project is None:
            raise ProjectContextError(
                f"persisted active project {stored_id} no longer exists"
            )
        return _project_result(project, "persisted")

    projects = project_store.list_projects(status="active")
    if not projects:
        projects = project_store.list_projects()
    if not projects:
        raise ProjectContextError("cannot establish an active project: no projects exist")

    default_project = projects[0]
    _write_active_project_id(default_project["id"])
    return _project_result(default_project, "defaulted_once")


def set_active_project(project_id: int) -> dict[str, Any]:
    """Validate and persist a new active project scope."""
    if isinstance(project_id, bool) or not isinstance(project_id, int) or project_id <= 0:
        raise ProjectContextError(f"project_id must be a positive integer, got {project_id!r}")
    project_store.init_db()
    project = project_store.get(project_id)
    if project is None:
        raise ProjectContextError(f"cannot activate project {project_id}: project does not exist")
    _write_active_project_id(project_id)
    return _project_result(project, "persisted")
