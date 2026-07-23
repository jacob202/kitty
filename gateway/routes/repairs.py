"""Self-repairs endpoint — actionable diagnosis for chat and Home cards.

Every repair item has a plain-English title, severity, and optional fix button
that dispatches through the action queue at T0 (auto-execute, logged).
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timedelta

from fastapi import APIRouter

logger = logging.getLogger("kitty.repairs")
router = APIRouter(tags=["repairs"])

_FIXABLE_THRESHOLD = 7 * 86400  # 7 days in seconds


@router.get("/repairs")
async def list_repairs():
    import os
    import pathlib
    import sys

    ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
    sys.path.insert(0, str(ROOT))

    try:
        from gateway.doctor import (
            Check,
            _check_disk,
            _check_env,
            _check_services,
            _check_venv,
            _check_mem0,
            _check_gateway_freshness,
            _check_codegraph,
            _load_env,
        )
    except ImportError:
        logger.error("cannot import doctor checks", exc_info=True)
        return {
            "ok": False,
            "error": "repairs engine unavailable",
            "repairs": [],
        }

    env = _load_env()
    checks: list[Check] = []
    checks.extend(_check_env(env))
    checks.extend(_check_disk())
    checks.extend(_check_services(env))
    checks.extend(_check_mem0(env))
    checks.extend(_check_venv())
    checks.extend(_check_codegraph())
    checks.extend(_check_gateway_freshness())
    checks.extend(_check_builder_health())
    checks.extend(_check_queue_backup_age())

    errors = [c for c in checks if c.level in ("FAIL", "WARN")]
    ok = len([c for c in checks if c.level == "FAIL"]) == 0

    return {
        "ok": ok,
        "checks_run": len(checks),
        "issues": len(errors),
        "repairs": [_to_repair(c) for c in checks],
    }


_PLAIN_ENGLISH: dict[str, str] = {
    "env:.env": "Environment file is missing",
    "env:api-keys": "There are no API keys configured",
    "env:single-key": "{detail}",
    "services:gateway": "The Kitty gateway is not responding",
    "services:litellm": "The LLM router is not responding",
    "services:chromadb": "The knowledge store is not reachable",
    "mem0:installed": "Mem0 is not installed",
    "mem0:broker": "Mem0 broker is not reachable",
    "venv:python": "The Python virtual environment may not match",
    "venv:requirements": "Python requirements are not installed",
    "disk:free": "Disk space is running low",
    "disk:data": "The data directory is missing",
    "codegraph:index": "CodeGraph index is stale or missing",
    "codegraph:auto-sync": "CodeGraph auto-sync is disabled",
    "gateway:freshness": "The gateway process is stale",
    "builder:stale-leases": "Builder has stale task leases",
    "builder:zombie-tasks": "Builder has zombie tasks",
    "queue:backup-age": "The queue backup is getting old",
}


def _to_repair(check) -> dict:
    level_map = {"PASS": "ok", "WARN": "warn", "FAIL": "error"}
    severity = level_map.get(check.level, "warn")
    detail = check.detail

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
        "services:gateway": "The gateway is running and answering",
        "services:litellm": "Model routing is live",
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
        "builder:stale-leases": "Builder leases are current",
        "builder:zombie-tasks": "No zombie tasks found",
        "queue:backup-age": "The queue backup is recent",
    }
    return passes.get(name, detail) if check.level == "PASS" else title


def _fix_action(check) -> dict | None:
    name = check.name
    detail = check.detail

    if "env" in name:
        return {
            "label": "View setup guide",
            "action_kind": "repair.check",
            "check_name": name,
        }

    if "services:gateway" in name:
        return {
            "label": "Check gateway again",
            "action_kind": "repair.check",
            "check_name": name,
        }

    if "services:litellm" in name:
        return {
            "label": "Check routing again",
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
            "label": "Check memory again",
            "action_kind": "repair.check",
            "check_name": name,
        }

    if "venv" in name:
        return {
            "label": "Check environment again",
            "action_kind": "repair.check",
            "check_name": name,
        }

    if "codegraph" in name:
        return {
            "label": "Recheck index",
            "action_kind": "repair.check",
            "check_name": name,
        }

    if "gateway:freshness" in name:
        return {
            "label": "Recheck gateway",
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
        from gateway.builder_queue import connect, stale_leases
        conn = connect()
        try:
            leases = stale_leases(conn)
            if leases:
                return [Check("WARN", "builder:stale-leases",
                              f"{len(leases)} stale lease(s) found — some tasks may be stuck")]
            return [Check("PASS", "builder:stale-leases",
                          "No stale leases")]
        except Exception as exc:
            return [Check("WARN", "builder:zombie-tasks",
                          f"Builder health check failed: {exc}")]
        finally:
            conn.close()
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

    from gateway.paths import DATA_DIR
    backup = DATA_DIR / "queue.db.backup"
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
    """Record a dismissed repair through the action queue."""
    repair_id = body.get("repair_id", "unknown")
    try:
        from gateway.action_queue import propose, execute
        action = propose(
            source_kind="repairs",
            kind="repair.dismiss",
            title=f"Repair dismissed: {repair_id}",
            preview=f"User dismissed a repair item: {repair_id}",
            payload={"label": repair_id, "check_name": repair_id},
        )
        execute(action["id"])
        return {"ok": True, "action_id": action["id"]}
    except Exception as exc:
        logger.warning("Failed to propose/execute dismiss action: %s", exc)
        return {"ok": False, "error": str(exc)}


@router.post("/repairs/check")
async def run_repair_check(body: dict):
    """Re-run a specific health check through the action queue."""
    check_name = body.get("check_name", "unknown")
    try:
        from gateway.action_queue import propose, execute
        action = propose(
            source_kind="repairs",
            kind="repair.check",
            title=f"Repair check: {check_name}",
            preview=f"User requested re-check of: {check_name}",
            payload={"check_name": check_name},
        )
        execute(action["id"])
        return {"ok": True, "action_id": action["id"]}
    except Exception as exc:
        logger.warning("Failed to propose/execute repair check: %s", exc)
        return {"ok": False, "error": str(exc)}
