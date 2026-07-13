"""Next-step navigator — one curated "B" per project (P4, docs/packets/016).

generate(project_id) asks an LLM for exactly one concrete next step from a
project's already-composed resume() state — the "B" in Jacob's "I know A,
I know Z, I just need to know B." Deliberately narrower than 021's
next_actions_json (mechanical top-3, no LLM): "B" is a single LLM-curated
pick with its own lifecycle, stored in its own table so 021's no-LLM
guarantee for next_actions_json stays true.

get(project_id) is a pure read. invalidate(project_id) clears the stored
step so the next refresh regenerates instead of showing a stale one —
exposed for whichever future surface resolves an action tied to a step
(see docs/packets/016 "too broad if": this packet does not auto-propose
such actions, so nothing calls invalidate() automatically yet).

D10: kind="code" projects are cloud-ok (git/commit text, not a local-only
class); every other kind defaults to local-only until a project names a
more specific content class — fail toward privacy, not away from it.

Public API:
  generate(project_id, llm_fn=None) -> dict
  get(project_id) -> dict | None
  invalidate(project_id) -> None
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any, Callable

from gateway import db as kitty_db
from gateway import project_resume, project_store, user_context
from gateway.paths import CONFIG_DIR, KITTY_DB_FILE

logger = logging.getLogger("kitty.next_step")

NEXT_STEP_DB_FILE = KITTY_DB_FILE

# Injected callable: (prompt, privacy_tier, content_class) -> raw model text.
# Parsing/validation is this module's job, same seam as triage.LlmFn.
LlmFn = Callable[[str, str, str | None], str]

# kind -> (privacy_tier, content_class). Anything not listed defaults to
# local-only (D10: fail toward privacy).
_PRIVACY_BY_KIND: dict[str, tuple[str, str | None]] = {
    "code": ("cloud_ok", None),
}
_DEFAULT_PRIVACY: tuple[str, str | None] = ("local", "health_admin")

_SYSTEM_PROMPT = (
    "You're Kitty: direct, honest, never flattering. For the project below, "
    "give exactly ONE concrete next step — small enough to start in five "
    "minutes, specific enough to act on today. Not a plan, not a list: one "
    "step. Also give one sentence on why it's next, one honest sentence on "
    "what's already done (if nothing notable happened, say so plainly — "
    "don't invent a win), and whether this step could be delegated to an "
    "agent (true/false).\n\n"
    'Reply with ONLY a JSON object: {"step": "...", "why": "...", '
    '"recent_win": "...", "delegable": true|false}'
)


class NextStepError(RuntimeError):
    """Raised when the model is unavailable or returns unusable output."""


def init_db() -> None:
    kitty_db.migrate(db_file=NEXT_STEP_DB_FILE)


def generate(project_id: int, llm_fn: LlmFn | None = None) -> dict[str, Any]:
    """Generate (or regenerate) the single next step for a project.

    Does not call project_resume.refresh() itself — the caller refreshes
    first so this always works from the latest composed state.
    """
    call = llm_fn or _default_llm
    init_db()

    project = project_store.get(project_id)
    if project is None:
        raise project_store.ProjectNotFound(f"no project with id {project_id}")

    resumed = project_resume.resume(project_id)
    previous = get(project_id)

    privacy_tier, content_class = _PRIVACY_BY_KIND.get(project["kind"], _DEFAULT_PRIVACY)
    prompt = _build_prompt(project, resumed)
    raw = call(prompt, privacy_tier, content_class)
    parsed = _parse_response(raw)

    generated_at = time.time()
    with kitty_db.connect(NEXT_STEP_DB_FILE) as conn:
        conn.execute(
            "INSERT INTO project_next_steps "
            "(project_id, step, why, recent_win, delegable, generated_at) "
            "VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(project_id) DO UPDATE SET "
            "step=excluded.step, why=excluded.why, recent_win=excluded.recent_win, "
            "delegable=excluded.delegable, generated_at=excluded.generated_at",
            (
                project_id,
                parsed["step"],
                parsed["why"],
                parsed.get("recent_win", ""),
                1 if parsed.get("delegable") else 0,
                generated_at,
            ),
        )
        conn.commit()

    changed = previous is None or previous["step"] != parsed["step"]
    return {
        "project_id": project_id,
        "step": parsed["step"],
        "why": parsed["why"],
        "recent_win": parsed.get("recent_win", ""),
        "delegable": bool(parsed.get("delegable")),
        "generated_at": generated_at,
        "changed": changed,
    }


def get(project_id: int) -> dict[str, Any] | None:
    init_db()
    with kitty_db.connect(NEXT_STEP_DB_FILE) as conn:
        row = conn.execute(
            "SELECT project_id, step, why, recent_win, delegable, generated_at "
            "FROM project_next_steps WHERE project_id = ?",
            (project_id,),
        ).fetchone()
    return _row_to_step(row) if row else None


def invalidate(project_id: int) -> None:
    """Clear the stored step so the next refresh regenerates it fresh."""
    init_db()
    with kitty_db.connect(NEXT_STEP_DB_FILE) as conn:
        conn.execute("DELETE FROM project_next_steps WHERE project_id = ?", (project_id,))
        conn.commit()


def _row_to_step(row: Any) -> dict[str, Any]:
    return {
        "project_id": row["project_id"],
        "step": row["step"],
        "why": row["why"],
        "recent_win": row["recent_win"] or "",
        "delegable": bool(row["delegable"]),
        "generated_at": row["generated_at"],
    }


def _build_prompt(project: dict[str, Any], resumed: dict[str, Any]) -> str:
    return (
        f"Project: {project['name']} ({project['kind']})\n"
        f"Current state: {resumed.get('summary') or 'no data yet'}\n"
        f"Open questions on record: {resumed.get('open_questions') or []}\n"
        f"Stored next actions (mechanical, context only): {resumed.get('next_actions') or []}"
    )


def _default_llm(prompt: str, privacy_tier: str, content_class: str | None) -> str:
    from gateway.llm_client import call_llm

    system = _SYSTEM_PROMPT
    context = user_context.load_user_context()
    prefs = _load_preferences()
    if context:
        system = f"{system}\n\n{context}"
    if prefs:
        system = f"{system}\n\n## Jacob's standing preferences\n\n{prefs}"

    return call_llm(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        max_tokens=400,
        temperature=0.3,
        response_format={"type": "json_object"},
        operation="next_step.generate",
        privacy_tier=privacy_tier,
        content_class=content_class,
    )


def _load_preferences() -> str:
    path = CONFIG_DIR / "PREFERENCES.md"
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise NextStepError(f"could not read preferences at {path}: {exc}") from exc


def _parse_response(raw: str) -> dict[str, Any]:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise NextStepError(f"model response was not valid JSON: {raw[:200]!r}") from exc
    if not isinstance(parsed, dict) or not str(parsed.get("step", "")).strip():
        raise NextStepError(f"model response missing 'step': {raw[:200]!r}")
    return parsed


def _is_self_development(project: dict[str, Any]) -> bool:
    """True if this code project is about Kitty itself (self-development).

    Per ADR 0016 only code projects whose name indicates Kitty work are
    considered self-development and get the "at most one" cap when life
    project steps are available.
    """
    if project.get("kind") != "code":
        return False
    name = (project.get("name") or "").lower()
    return "kitty" in name


def select_steps(limit: int = 3) -> list[dict[str, Any]]:
    """Select next steps with life-first ordering (ADR 0016).

    Life projects (kind != "code") are preferred over code projects when both
    have eligible stored steps.  At most one Kitty-self-development suggestion
    may surface while any life-project step is available.

    Returns the same dict shape as brief.py's get_next_steps_section():
    project_id, project_name, step, why.
    """
    from gateway import project_store

    projects = [p for p in project_store.list_projects() if p["status"] == "active"]

    life: list[dict[str, Any]] = []
    other_code: list[dict[str, Any]] = []
    self_dev: list[dict[str, Any]] = []

    for project in projects:
        step = get(project["id"])
        if step is None:
            continue
        entry = {
            "project_id": project["id"],
            "project_name": project["name"],
            "step": step["step"],
            "why": step["why"],
        }
        if project["kind"] != "code":
            life.append(entry)
        elif _is_self_development(project):
            self_dev.append(entry)
        else:
            other_code.append(entry)

    # Assemble: life first, then other code, then at most 1 self-dev.
    result: list[dict[str, Any]] = []
    result.extend(life)
    result.extend(other_code)
    if life and self_dev:
        # At most one self-dev suggestion when life steps are present.
        result.append(self_dev[0])
    elif not life and self_dev:
        # No life steps — all self-dev steps are fine.
        result.extend(self_dev)

    return result[:limit]
