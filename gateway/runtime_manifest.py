"""Authoritative runtime facts exposed to Kitty clients and chat turns.

This is deliberately a read-side composer. Each fact carries its owner,
observation time, expiry, and an explicit state so a failed probe cannot be
mistaken for an unavailable feature or a successful operation.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import sqlite3
import subprocess
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from gateway import builder_runtime, project_store
from gateway.http_client import get_http_client
from gateway.llm_client import PROVIDERS
from gateway.paths import ACTION_TIERS_FILE, LITELLM_BASE, LITELLM_KEY, ROOT

logger = logging.getLogger("kitty.runtime_manifest")

SCHEMA_VERSION = 1
MANIFEST_TTL_SECONDS = 15


class RuntimeManifestError(RuntimeError):
    """Raised when a requested runtime fact cannot be represented safely."""


def _timestamp(now: datetime) -> str:
    return now.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _fact(
    value: Any,
    *,
    source: str,
    observed_at: str,
    valid_until: str,
    state: str = "available",
    reason: str | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "state": state,
        "value": value,
        "source": source,
        "observed_at": observed_at,
        "valid_until": valid_until,
    }
    if reason:
        result["reason"] = reason
    return result


def _unknown(
    *,
    source: str,
    observed_at: str,
    valid_until: str,
    reason: str,
) -> dict[str, Any]:
    logger.warning("Runtime fact unknown (%s): %s", source, reason)
    return _fact(
        None,
        source=source,
        observed_at=observed_at,
        valid_until=valid_until,
        state="unknown",
        reason=reason,
    )


def _git_snapshot() -> dict[str, Any]:
    def run(args: list[str]) -> str:
        result = subprocess.run(
            ["git", *args],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
            timeout=3,
        )
        return result.stdout.strip()

    status = run(["status", "--porcelain"])
    return {
        "root": str(ROOT),
        "branch": run(["branch", "--show-current"]),
        "commit": run(["rev-parse", "HEAD"]),
        "dirty": bool(status),
        "changed_paths": len(status.splitlines()) if status else 0,
    }


def _project_fact(
    project_id: int | None,
    *,
    observed_at: str,
    valid_until: str,
) -> dict[str, Any]:
    if project_id is None:
        from gateway.project_context import ProjectContextError, get_active_project

        try:
            project_id = get_active_project()["project_id"]
        except (OSError, RuntimeError, ValueError, ProjectContextError) as exc:
            return _unknown(
                source="project_context",
                observed_at=observed_at,
                valid_until=valid_until,
                reason=f"active project could not be established: {exc}",
            )
    if project_id <= 0:
        raise RuntimeManifestError(f"project_id must be positive, got {project_id}")
    project = project_store.get(project_id)
    if project is None:
        return _fact(
            None,
            source="project_store",
            observed_at=observed_at,
            valid_until=valid_until,
            state="unavailable",
            reason=f"project {project_id} does not exist",
        )
    return _fact(project, source="project_store", observed_at=observed_at, valid_until=valid_until)


async def _litellm_models(
    *,
    observed_at: str,
    valid_until: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Probe LiteLLM once and return model availability plus connection health."""
    try:
        client = await get_http_client()
        response = await client.get(
            f"{LITELLM_BASE}/v1/models",
            headers={"Authorization": f"Bearer {LITELLM_KEY}"},
            timeout=1.5,
        )
        if response.status_code != 200:
            detail = response.text[:300].replace("\n", " ")
            raise RuntimeManifestError(
                f"LiteLLM model probe returned HTTP {response.status_code}: {detail}"
            )
        payload = response.json()
        rows = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(rows, list):
            raise RuntimeManifestError("LiteLLM model probe returned no data list")
        models = [row["id"] for row in rows if isinstance(row, dict) and isinstance(row.get("id"), str)]
        if not models:
            raise RuntimeManifestError("LiteLLM model probe returned an empty model list")
        return (
            _fact(models, source="litellm:/v1/models", observed_at=observed_at, valid_until=valid_until),
            _fact(
                {"endpoint": LITELLM_BASE, "model_count": len(models)},
                source="litellm:/v1/models",
                observed_at=observed_at,
                valid_until=valid_until,
            ),
        )
    except (httpx.HTTPError, RuntimeManifestError, OSError, ValueError) as exc:
        reason = f"LiteLLM probe failed: {exc}"
        return (
            _unknown(
                source="litellm:/v1/models",
                observed_at=observed_at,
                valid_until=valid_until,
                reason=reason,
            ),
            _unknown(
                source="litellm:/v1/models",
                observed_at=observed_at,
                valid_until=valid_until,
                reason=reason,
            ),
        )


def _provider_facts(*, observed_at: str, valid_until: str) -> list[dict[str, Any]]:
    providers: list[dict[str, Any]] = []
    for provider_id, config in PROVIDERS.items():
        configured = any(bool(os.environ.get(name, "").strip()) for name in config.api_key_env)
        providers.append(
            {
                "id": provider_id,
                "route": config.route,
                "configuration": "configured" if configured else "unconfigured",
                "default_model": config.model_default or None,
                "observed_at": observed_at,
                "valid_until": valid_until,
                "state": "unknown" if configured else "unavailable",
                "reason": (
                    "configuration is present; live provider health is not probed in KPA-01"
                    if configured
                    else "no configured credential was found"
                ),
            }
        )
    return providers


def _builder_fact(*, observed_at: str, valid_until: str) -> dict[str, Any]:
    enabled = os.environ.get("KITTY_BUILDER_QUEUE_ENABLED", "1").strip().lower()
    if enabled in {"0", "false", "no", "off"}:
        return _fact(
            None,
            source="builder_queue",
            observed_at=observed_at,
            valid_until=valid_until,
            state="unavailable",
            reason="KITTY_BUILDER_QUEUE_ENABLED disables the Builder queue",
        )
    try:
        snapshot = builder_runtime.build_runtime_snapshot()
        partial_packets = snapshot["integrity"]["partial_packets"]
        if partial_packets:
            noun = "record" if partial_packets == 1 else "records"
            return _fact(
                snapshot,
                source="builder_runtime",
                observed_at=observed_at,
                valid_until=valid_until,
                state="degraded",
                reason=(
                    f"Builder status includes {partial_packets} partial packet {noun}."
                ),
            )
        return _fact(
            snapshot,
            source="builder_runtime",
            observed_at=observed_at,
            valid_until=valid_until,
        )
    except (OSError, RuntimeError, ValueError, sqlite3.Error) as exc:
        return _unknown(
            source="builder_runtime",
            observed_at=observed_at,
            valid_until=valid_until,
            reason=f"Builder state read failed: {exc}",
        )


def _grant_posture() -> dict[str, Any]:
    """Standing user grants, summarized for a model turn (issue #554).

    An unreadable grant store reports itself as unknown. Returning "no grants"
    instead would read to a turn as "nothing is restricted and nothing is
    pre-authorized", which is the one wrong answer here.
    """
    try:
        from gateway import action_grants
    except ImportError as exc:  # pragma: no cover - import wiring fault
        return {"state": "unknown", "reason": f"grant module unavailable: {exc}"}
    try:
        posture = action_grants.approval_posture()
    except Exception as exc:
        logger.warning("Grant posture unavailable: %s", exc)
        return {"state": "unknown", "reason": f"grant store read failed: {exc}"}
    return {"state": "available", **posture}


def _approval_fact(*, observed_at: str, valid_until: str) -> dict[str, Any]:
    try:
        raw = json.loads(ACTION_TIERS_FILE.read_text())
        if not isinstance(raw, dict):
            raise RuntimeManifestError(f"{ACTION_TIERS_FILE} must contain a JSON object")
        tiers = {key: value for key, value in raw.items() if not key.startswith("_")}
        disabled = raw.get("_disabled_v1", [])
        if not isinstance(disabled, list) or not all(isinstance(item, str) for item in disabled):
            raise RuntimeManifestError(f"{ACTION_TIERS_FILE} has an invalid _disabled_v1 list")
        return _fact(
            {
                "policy_version": "action_tiers.json",
                "tiers": tiers,
                "disabled": disabled,
                "auto_execute_tiers": ["T0", "T1"],
                "approval_required_tiers": ["T2"],
                "grants": _grant_posture(),
            },
            source=str(ACTION_TIERS_FILE),
            observed_at=observed_at,
            valid_until=valid_until,
        )
    except (OSError, ValueError, RuntimeManifestError) as exc:
        return _unknown(
            source=str(ACTION_TIERS_FILE),
            observed_at=observed_at,
            valid_until=valid_until,
            reason=f"approval policy read failed: {exc}",
        )


def _tool_fact(*, observed_at: str, valid_until: str) -> dict[str, Any]:
    # These are gateway-owned command surfaces, not a claim that every remote
    # integration is healthy. Remote tool health is represented separately.
    tools = [
        {"id": "chat.completions", "display_name": "Chat", "approval_class": "read"},
        {"id": "knowledge.search", "display_name": "Knowledge search", "approval_class": "read"},
        {"id": "projects.resume", "display_name": "Project resume", "approval_class": "read"},
        {"id": "builder.initiative", "display_name": "Builder initiatives", "approval_class": "bounded_write"},
    ]
    return _fact(tools, source="gateway route registry", observed_at=observed_at, valid_until=valid_until)


async def compose_manifest(project_id: int | None = None) -> dict[str, Any]:
    """Compose one authoritative, revisioned runtime snapshot."""
    now = datetime.now(timezone.utc)
    observed_at = _timestamp(now)
    valid_until = _timestamp(now + timedelta(seconds=MANIFEST_TTL_SECONDS))

    try:
        repository = _fact(
            await asyncio.to_thread(_git_snapshot),
            source="git",
            observed_at=observed_at,
            valid_until=valid_until,
        )
    except (OSError, subprocess.SubprocessError, UnicodeError) as exc:
        repository = _unknown(
            source="git",
            observed_at=observed_at,
            valid_until=valid_until,
            reason=f"repository probe failed: {exc}",
        )

    models, litellm = await _litellm_models(observed_at=observed_at, valid_until=valid_until)
    timezone_name = datetime.now().astimezone().tzname() or "unknown"
    app_version = os.environ.get("KITTY_VERSION", "").strip() or None
    app_version_fact = (
        _fact(app_version, source="KITTY_VERSION", observed_at=observed_at, valid_until=valid_until)
        if app_version
        else _unknown(
            source="KITTY_VERSION",
            observed_at=observed_at,
            valid_until=valid_until,
            reason="KITTY_VERSION is not configured",
        )
    )

    body: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": observed_at,
        "valid_until": valid_until,
        "application": {
            "name": "Kitty",
            "version": app_version_fact,
            "build_commit": repository.get("value", {}).get("commit") if repository["state"] == "available" else None,
            "environment": os.environ.get("KITTY_ENV", "local"),
        },
        "clock": _fact(
            {"current_time": observed_at, "timezone": timezone_name},
            source="host clock",
            observed_at=observed_at,
            valid_until=valid_until,
        ),
        "context": {
            "active_project": _project_fact(project_id, observed_at=observed_at, valid_until=valid_until),
            "repository": repository,
        },
        "execution": {"builder": _builder_fact(observed_at=observed_at, valid_until=valid_until)},
        "inference": {
            "routing_mode": "gateway route_model + LiteLLM",
            "available_models": models,
            "providers": _provider_facts(observed_at=observed_at, valid_until=valid_until),
            "execution_location": "local gateway with provider-dependent model execution",
        },
        "tools": _tool_fact(observed_at=observed_at, valid_until=valid_until),
        "connections": {
            "gateway": _fact(
                {"endpoint": "local gateway", "state": "serving"},
                source="runtime manifest request",
                observed_at=observed_at,
                valid_until=valid_until,
            ),
            "litellm": litellm,
        },
        "approvals": _approval_fact(observed_at=observed_at, valid_until=valid_until),
    }
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    revision = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]
    return {
        **body,
        "manifest_id": f"runtime-{revision}",
        "revision": revision,
    }


def _summarize_builder_fact(fact: dict[str, Any]) -> dict[str, Any]:
    """Drop the initiative bodies from a Builder fact, keeping the counts.

    The full snapshot carries every initiative record — 400KB+ on Jacob's Mac —
    and inlining it made every chat turn pay ~107k tokens of prompt it never
    reads. A turn only needs to know how much work is queued and whether the
    projection is trustworthy; `./kitty builder ... --json` remains the place to
    read initiative detail.
    """
    snapshot = fact.get("value")
    if not isinstance(snapshot, dict):
        return fact

    initiatives = snapshot.get("initiatives")
    summary = {
        key: value for key, value in snapshot.items() if key != "initiatives"
    }
    summary["initiative_count"] = (
        len(initiatives) if isinstance(initiatives, (list, dict)) else 0
    )
    return {**fact, "value": summary}


def _compact_runtime_fact(value: Any) -> Any:
    """Keep fact truth while removing provenance duplicated by the manifest envelope."""
    if not isinstance(value, dict):
        return value
    if "state" in value and ("value" in value or "reason" in value):
        compact: dict[str, Any] = {"state": value.get("state")}
        if "value" in value:
            compact["value"] = value.get("value")
        if value.get("reason"):
            compact["reason"] = value["reason"]
        return compact
    return {key: _compact_runtime_fact(child) for key, child in value.items()}


def _compact_runtime_status(value: Any) -> Any:
    """Keep only availability state/reason for operational capability surfaces."""
    if not isinstance(value, dict):
        return value
    if "state" in value:
        compact: dict[str, Any] = {"state": value.get("state")}
        if value.get("reason"):
            compact["reason"] = value["reason"]
        return compact
    return {key: _compact_runtime_status(child) for key, child in value.items()}


def compact_runtime_context(manifest: dict[str, Any]) -> str:
    """Render the bounded runtime truth a model turn actually needs.

    The top-level manifest revision/freshness owns provenance for the whole
    snapshot, so repeating source/observed/expiry on every nested fact only
    consumes prompt budget. Tool registry, connection diagnostics, and approval
    policy remain enforced/exposed by their owning runtime surfaces rather than
    being repeated in every chat prompt.
    """
    execution = manifest["execution"]
    builder = execution.get("builder")
    if isinstance(builder, dict):
        execution = {**execution, "builder": _summarize_builder_fact(builder)}

    context = {
        "manifest_revision": manifest["revision"],
        "generated_at": manifest["generated_at"],
        "valid_until": manifest["valid_until"],
        "application": _compact_runtime_fact(manifest["application"]),
        "clock": _compact_runtime_fact(manifest["clock"]),
        "context": _compact_runtime_fact(manifest["context"]),
        "execution": _compact_runtime_fact(execution),
        "inference": _compact_runtime_fact({
            "routing_mode": manifest["inference"]["routing_mode"],
            "available_models": manifest["inference"]["available_models"],
            "execution_location": manifest["inference"]["execution_location"],
        }),
        "tools": _compact_runtime_status(manifest["tools"]),
        "connections": _compact_runtime_status(manifest["connections"]),
        "approvals": _compact_runtime_status(manifest["approvals"]),
    }
    return (
        "<kitty_runtime_truth>\n"
        + json.dumps(context, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        + "\n</kitty_runtime_truth>"
    )
