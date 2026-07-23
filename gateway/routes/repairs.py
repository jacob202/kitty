"""Self-repairs endpoint — actionable diagnosis for chat and Home cards.

Exposes GET /repairs: runs the same checks as kitty doctor but returns
structured repair items with fix suggestions that the UI can render as
buttons. Does NOT auto-execute — proposals go through the action queue.
"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter

logger = logging.getLogger("kitty.repairs")
router = APIRouter(tags=["repairs"])


@router.get("/repairs")
async def list_repairs():
    """Run the full doctor check and return structured repair items.

    Each repair has: id, severity (ok/warn/error), title, detail, and an
    optional fix suggestion with a label + command the UI can offer as a
    button. Severity 'ok' items are informational only (no fix needed).
    """
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

    errors = [c for c in checks if c.level in ("FAIL", "WARN")]
    ok = len([c for c in checks if c.level == "FAIL"]) == 0

    return {
        "ok": ok,
        "checks_run": len(checks),
        "issues": len(errors),
        "repairs": [_to_repair(c) for c in checks],
    }


def _to_repair(check) -> dict:
    level_map = {"PASS": "ok", "WARN": "warn", "FAIL": "error"}
    repair = {
        "id": check.name.replace(":", "-"),
        "name": check.name,
        "severity": level_map.get(check.level, "warn"),
        "detail": check.detail,
    }

    if check.level == "PASS":
        return repair

    repair["fix"] = _fix_suggestion(check)
    return repair


def _fix_suggestion(check) -> dict | None:
    name = check.name
    detail = check.detail

    if "venv" in name and "run:" in detail:
        return {
            "label": "Create virtual environment",
            "description": "python3.12 -m venv venv && venv/bin/pip install -r requirements.txt",
        }

    if "gateway" in name and not _http_ok("http://127.0.0.1:8000/health"):
        return {
            "label": "Start gateway",
            "description": "./kitty up (starts Gateway and LiteLLM)",
        }

    if "litellm" in name:
        return {
            "label": "Restart services",
            "description": "./kitty down && ./kitty up",
        }

    if "disk" in name and "low" in detail.lower():
        return {
            "label": "Free disk space",
            "description": "Clear caches, remove unused docker images, or archive old projects",
        }

    if "mem0" in name:
        return {
            "label": "Install mem0",
            "description": "venv/bin/pip install mem0ai (runs in local mode without API key)",
        }

    return None


def _http_ok(url: str, timeout: float = 3.0) -> bool:
    try:
        import urllib.request
        req = urllib.request.Request(url, method="HEAD")
        urllib.request.urlopen(req, timeout=timeout)
        return True
    except Exception:
        return False
