"""Self-repairs endpoint — actionable diagnosis for chat and Home cards.

Every repair item has a plain-English title, severity, and optional fix button
that dispatches through the action queue at T0 (auto-execute, logged).
"""

from __future__ import annotations

import logging
import time

from fastapi import APIRouter

from gateway import action_queue, builder_queue, paths, signal_store

logger = logging.getLogger("kitty.repairs")
router = APIRouter(tags=["repairs"])

_FIXABLE_THRESHOLD = 7 * 86400  # 7 days in seconds


@router.get("/repairs")
def list_repairs():
    import pathlib
    import sys

    ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
    sys.path.insert(0, str(ROOT))

    try:
        from gateway import doctor
    except ImportError:
        logger.error("cannot import doctor checks", exc_info=True)
        return {
            "ok": False,
            "error": "repairs engine unavailable",
            "repairs": [],
        }

    env = doctor.load_env()
    checks: list[doctor.Check] = []
    checks.extend(doctor.check_env(env))
    checks.extend(doctor.check_disk())
    checks.extend(doctor.check_services(env))
    checks.extend(doctor.check_mem0(env))
    checks.extend(doctor.check_venv())
    checks.extend(doctor.check_codegraph())
    checks.extend(doctor.check_gateway_freshness())
    checks.extend(_check_builder_health())
    checks.extend(_check_queue_backup_age())

    errors = [c for c in checks if c.level in ("FAIL", "WARN")]
    ok = len([c for c in checks if c.level == "FAIL"]) == 0

    return {
        "ok": ok,
        "checks_run": len(checks),
        "issues": len(errors),
        "repairs": [to_repair(c) for c in checks],
    }


_PLAIN_ENGLISH: dict[str, str] = {
    "env:.env": "Kitty setup needs attention",
    "env:api-keys": "A model provider needs setup",
    "env:single-key": "A model provider needs setup",
    "env:llm_key": "A model provider needs setup",
    "env:gateway_secret": "Kitty protection needs setup",
    "env:telegram_token": "Telegram is not connected",
    "env:parse": "Some setup needs attention",
    "service:gateway": "Kitty's core service is unavailable",
    "service:litellm": "Model routing is temporarily unavailable",
    "services:chromadb": "The knowledge store is not reachable",
    "store:chromadb": "The knowledge store needs attention",
    "store:mem0": "Memory search is temporarily unavailable",
    "mem0:installed": "Memory search needs setup",
    "mem0:broker": "Memory search is temporarily unavailable",
    "venv:python": "A background service needs setup",
    "venv:requirements": "A background service needs setup",
    "runtime:venv": "A background service needs setup",
    "disk:free": "Disk space is running low",
    "disk:data": "Kitty storage needs attention",
    "disk:data_dir": "Kitty storage needs attention",
    "codegraph:index": "Search indexing needs attention",
    "codegraph:auto-sync": "Search indexing needs attention",
    "codegraph:daemon": "Search indexing needs attention",
    "codegraph:index_freshness": "Search indexing needs attention",
    "gateway:freshness": "Kitty's core service needs attention",
    "runtime:gateway_freshness": "Kitty's core service needs attention",
    "builder:silent-transitions": "Builder has incomplete transition history",
    "builder:zombie-tasks": "Builder has zombie tasks",
    "queue:backup-age": "The queue backup is getting old",
}

_INTERNAL_DETAIL_MARKERS = (
    ".env",
    "/Users/",
    "/private/",
    "http://",
    "https://",
    "127.0.0.1",
    "API_KEY",
    "TOKEN",
    "SECRET",
    "python3",
    "pip install",
    "kitty up",
    "./kitty",
    "POST /",
    "GET /",
    "PUT /",
    "PATCH /",
    "DELETE /",
    "venv/bin",
    "requirements.txt",
)


def _public_detail(check) -> str:
    detail = str(check.detail or "")
    name = str(check.name)
    if check.level == "PASS":
        positive = {
            "service:gateway": "Kitty's core service is responding.",
            "service:litellm": "Model routing is responding.",
            "store:mem0": "Memory search is available.",
            "runtime:venv": "Background services are ready.",
            "codegraph:index": "Search indexing is available.",
        }
        if name in positive:
            return positive[name]
        if not any(marker.lower() in detail.lower() for marker in _INTERNAL_DETAIL_MARKERS):
            return detail
        return "Check passed."
    if name.startswith("env:"):
        return "Kitty's configuration needs attention."
    if name == "service:gateway":
        return "Kitty could not reach a core service."
    if name == "service:litellm":
        return "Model routing is not responding right now."
    if name.startswith("service:"):
        return "A Kitty service needs attention."
    if name.startswith(("store:mem0", "mem0:")):
        return "Memory search is unavailable right now."
    if name.startswith(("store:", "services:", "mem0:")):
        return "A local data service needs attention."
    if name.startswith(("runtime:", "venv:")):
        return "A background service needs setup."
    if name.startswith("disk:"):
        return "Kitty's local storage needs attention."
    if name.startswith("codegraph:"):
        return "Search indexing needs attention."
    if not any(marker.lower() in detail.lower() for marker in _INTERNAL_DETAIL_MARKERS):
        return detail
    return "Technical details are available in diagnostics."


def to_repair(check) -> dict:
    """Translate a doctor `Check` into the repair card the UI renders.

    Public because the repairs engine is not the only consumer: the chat
    context builder folds the same cards into a prompt, and the hermetic
    kitty-chat gateway replays them. Detail text is scrubbed of internal
    paths and hostnames — this dict crosses to the browser.
    """
    level_map = {"PASS": "ok", "WARN": "warn", "FAIL": "error"}
    severity = level_map.get(check.level, "warn")
    detail = _public_detail(check)

    title = _PLAIN_ENGLISH.get(check.name)
    if title is None:
        title = check.name.replace(":", " ").replace("-", " ")
    else:
        title = title.format(detail=detail)

    repair: dict = {
        "id": check.name.replace(":", "-").replace(".", "-"),
        "severity": severity,
        "title": title,
        "detail": detail,
    }

    if check.level == "PASS":
        repair["title"] = _pass_title(check.name, detail)
        return repair

    repair["fix"] = _fix_action(check)
    return repair


def _pass_title(name: str, detail: str) -> str:
    passes: dict[str, str] = {
        "env:.env": "Environment file is set up",
        "env:api-keys": "API keys are configured",
        "service:gateway": "The gateway is running and answering",
        "service:litellm": "Model routing is live",
        "services:chromadb": "The knowledge store is reachable",
        "mem0:installed": "Mem0 is installed",
        "mem0:broker": "Mem0 broker is reachable",
        "venv:python": "Python environment is healthy",
        "venv:requirements": "Python requirements are installed",
        "disk:free": "There is plenty of disk space",
        "disk:data": "The data directory exists",
        "codegraph:index": "CodeGraph index is up to date",
        "codegraph:auto-sync": "CodeGraph is watching for changes",
        "gateway:freshness": "The gateway process is fresh",
        "builder:silent-transitions": "Builder transition history is complete",
        "builder:zombie-tasks": "No zombie tasks found",
        "queue:backup-age": "The queue backup is recent",
    }
    fallback = name.replace(":", " ").replace("-", " ")
    return passes.get(name, f"{fallback} looks okay")


def _fix_action(check) -> dict | None:
    name = check.name

    if name.startswith("env:"):
        return {
            "label": "View setup guide",
            "action_kind": "repair.check",
            "check_name": name,
        }

    if "service:gateway" in name:
        return {
            "label": "Try again",
            "action_kind": "repair.check",
            "check_name": name,
        }

    if "service:litellm" in name:
        return {
            "label": "Try again",
            "action_kind": "repair.check",
            "check_name": name,
        }

    if "services" in name and "chromadb" in name:
        return {
            "label": "Check knowledge store again",
            "action_kind": "repair.check",
            "check_name": name,
        }

    if "disk" in name:
        return {
            "label": "Check disk again",
            "action_kind": "repair.check",
            "check_name": name,
        }

    if "mem0" in name:
        return {
            "label": "Try again",
            "action_kind": "repair.check",
            "check_name": name,
        }

    if "venv" in name:
        return {
            "label": "Try again",
            "action_kind": "repair.check",
            "check_name": name,
        }

    if "codegraph" in name:
        return {
            "label": "Try again",
            "action_kind": "repair.check",
            "check_name": name,
        }

    if "gateway:freshness" in name:
        return {
            "label": "Try again",
            "action_kind": "repair.check",
            "check_name": name,
        }

    if "builder" in name or "queue" in name:
        return {
            "label": "Recheck Builder",
            "action_kind": "repair.check",
            "check_name": name,
        }

    return None


def _check_builder_health() -> list:
    from dataclasses import dataclass

    @dataclass
    class Check:
        level: str
        name: str
        detail: str

    try:

        transitions = builder_queue.find_silent_transitions()
        if transitions:
            return [Check(
                "WARN",
                "builder:silent-transitions",
                f"{len(transitions)} task(s) changed state without transition history",
            )]
        return [Check(
            "PASS",
            "builder:silent-transitions",
            "Every transitioned task has an event trail",
        )]
    except Exception as exc:
        return [Check("WARN", "builder:zombie-tasks",
                      f"Cannot reach Builder database: {exc}")]


def _check_queue_backup_age() -> list:
    from dataclasses import dataclass

    @dataclass
    class Check:
        level: str
        name: str
        detail: str

    backup = paths.DATA_DIR / "queue.db.backup"
    if not backup.exists():
        return [Check("PASS", "queue:backup-age", "No queue backup found — not applicable")]
    age_seconds = time.time() - backup.stat().st_mtime
    age_days = age_seconds / 86400
    if age_seconds > _FIXABLE_THRESHOLD:
        return [Check("WARN", "queue:backup-age",
                      f"Queue backup is {age_days:.1f} days old — may be stale")]
    return [Check("PASS", "queue:backup-age",
                  f"Queue backup is {age_days:.1f} day(s) old")]


@router.post("/repairs/dismiss")
async def dismiss_repair(body: dict):
    """Record a dismissed repair through the action queue. Signal-* IDs mark
    the signal processed so it doesn't reappear on next poll."""
    repair_id = body.get("repair_id", "unknown")
    try:

        if isinstance(repair_id, str) and repair_id.startswith("signal-"):
            signal_id_str = repair_id.replace("signal-", "", 1)
            try:
                signal_id = int(signal_id_str)
            except ValueError as exc:
                raise ValueError(
                    f"signal repair id {repair_id!r} has a non-numeric signal id"
                ) from exc

            # Must not be swallowed: an unmarked signal reappears on the next
            # poll, so a silently failed mark reports a dismissal that did not
            # happen.
            signal_store.mark_processed(signal_id)

        action = action_queue.propose(
            source_kind="repairs",
            kind="repair.dismiss",
            title=f"Repair dismissed: {repair_id}",
            preview=f"User dismissed a repair item: {repair_id}",
            payload={"label": repair_id, "check_name": repair_id},
        )
        action_queue.execute(action["id"])
        return {"ok": True, "action_id": action["id"]}
    except Exception as exc:
        logger.warning("Failed to propose/execute dismiss action: %s", exc)
        return {"ok": False, "error": str(exc)}


@router.post("/repairs/check")
async def run_repair_check(body: dict):
    """Re-run a specific health check through the action queue."""
    check_name = body.get("check_name", "unknown")
    try:
        action = action_queue.propose(
            source_kind="repairs",
            kind="repair.check",
            title=f"Repair check: {check_name}",
            preview=f"User requested re-check of: {check_name}",
            payload={"check_name": check_name},
        )
        action_queue.execute(action["id"])
        return {"ok": True, "action_id": action["id"]}
    except Exception as exc:
        logger.warning("Failed to propose/execute repair check: %s", exc)
        return {"ok": False, "error": str(exc)}
