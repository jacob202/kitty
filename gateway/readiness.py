"""Production readiness facts for the Kitty golden path.

Liveness and readiness are deliberately separate. ``/health`` only answers
"is the Gateway process serving?". This module answers whether the production
slice has the minimum prerequisites to accept real chat + Builder work without
spending a model call just to probe health.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

from gateway.builder_doctor import Check, _check_database
from gateway.http_client import get_http_client
from gateway.model_routing import describe_providers

ROOT = Path(__file__).resolve().parent.parent


def _git(args: list[str], cwd: Path) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or f"git {' '.join(args)} failed")
    return completed.stdout


def repository_status(
    root: Path = ROOT,
    *,
    expected_commit: str | None = None,
) -> dict[str, Any]:
    """Fail closed when the serving checkout is dirty or not the deployed SHA."""
    try:
        commit = _git(["rev-parse", "HEAD"], root).strip()
        dirty_lines = [
            line
            for line in _git(["status", "--porcelain", "--untracked-files=normal"], root).splitlines()
            if line.strip()
        ]
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        return {
            "ready": False,
            "commit": None,
            "dirty": None,
            "reason": f"repository probe failed: {type(exc).__name__}: {exc}",
        }

    expected = (expected_commit or "").strip()
    if dirty_lines:
        return {
            "ready": False,
            "commit": commit,
            "dirty": True,
            "changed_paths": len(dirty_lines),
            "reason": "serving repository is dirty",
        }
    if expected and commit != expected:
        return {
            "ready": False,
            "commit": commit,
            "dirty": False,
            "expected_commit": expected,
            "reason": f"serving repository does not match expected commit {expected}",
        }
    return {
        "ready": True,
        "commit": commit,
        "dirty": False,
        "expected_commit": expected or None,
        "reason": "clean serving repository matches deployment expectation",
    }


async def _local_provider_reachable(base_url: str) -> bool:
    url = f"{base_url.rstrip('/')}/models"
    try:
        client = await get_http_client()
        response = await client.get(url, timeout=1.5)
        return 200 <= response.status_code < 300
    except Exception:  # noqa: BLE001 — any transport/protocol failure means local route is not ready
        return False


async def chat_status() -> dict[str, Any]:
    """Return zero-spend chat route readiness.

    Remote routes are configuration probes only: a present credential is enough
    to say the route is wired, while the external golden-path smoke remains the
    proof that the account/model/credit is actually usable. Local routes have no
    credential, so they must answer their OpenAI-compatible ``/models`` endpoint.
    """
    description = describe_providers()
    active = str(description.get("active") or "auto")
    providers = [
        p
        for p in description.get("providers", [])
        if bool(p.get("configured")) and not bool(p.get("disabled"))
    ]
    configured = [str(p.get("name")) for p in providers]

    if active != "auto":
        providers = [p for p in providers if str(p.get("name")) == active]

    usable: list[str] = []
    local_unreachable: list[str] = []
    for provider in providers:
        name = str(provider.get("name"))
        if str(provider.get("kind")) == "local":
            if await _local_provider_reachable(str(provider.get("base_url") or "")):
                usable.append(name)
            else:
                local_unreachable.append(name)
        else:
            usable.append(name)

    ready = bool(usable)
    if ready:
        reason = f"usable route(s): {', '.join(usable)}"
    elif active != "auto":
        reason = f"selected provider {active!r} is not usable"
    elif local_unreachable:
        reason = f"configured local route(s) unreachable: {', '.join(local_unreachable)}"
    else:
        reason = "no configured and enabled chat route"

    return {
        "ready": ready,
        "active": active,
        "configured": configured,
        "usable": usable,
        "local_unreachable": local_unreachable,
        "probe_mode": "configuration-only for remote providers",
        "reason": reason,
    }


def _builder_database_checks() -> list[Check]:
    return _check_database(None)


def builder_status() -> dict[str, Any]:
    """Require a real, integrity-checked Builder DB for production work."""
    checks = _builder_database_checks()
    db_open = any(c.name == "db:open" and c.level == "PASS" for c in checks)
    integrity_ok = any(c.name == "db:integrity_check" and c.level == "PASS" for c in checks)
    failures = [c.detail for c in checks if c.level == "FAIL"]
    ready = db_open and integrity_ok and not failures
    return {
        "ready": ready,
        "checks": [{"level": c.level, "name": c.name, "detail": c.detail} for c in checks],
        "reason": "Builder database integrity is healthy" if ready else "Builder database is not production-ready",
    }


def auth_status() -> dict[str, Any]:
    configured = bool(os.environ.get("GATEWAY_SECRET", "").strip())
    if os.environ.get("KITTY_ENV") == "test":
        return {"ready": True, "configured": configured, "reason": "explicit test environment"}
    return {
        "ready": configured,
        "configured": configured,
        "reason": "Gateway bearer configured" if configured else "GATEWAY_SECRET is missing",
    }


async def readiness_snapshot() -> dict[str, Any]:
    components = {
        "auth": auth_status(),
        "repository": repository_status(
            expected_commit=os.environ.get("KITTY_EXPECTED_COMMIT", "").strip() or None
        ),
        "chat": await chat_status(),
        "builder": builder_status(),
    }
    blockers = [name for name, value in components.items() if not bool(value.get("ready"))]
    ready = not blockers
    return {
        "status": "ready" if ready else "not_ready",
        "ready": ready,
        "service": "kitty-gateway",
        "blockers": blockers,
        "components": components,
    }
