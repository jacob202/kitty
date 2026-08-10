"""Read-only Kitty/Builder projections for conversational MCP clients."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from gateway.builder_status_readonly import (
    build_status_snapshot_readonly,
    get_initiative_readonly as get_initiative,
)
from gateway.context_receipt import build_context_receipt

from .repo_tools import repo_root
from .schemas import MCP_ARTIFACT_MARKER, receipt


def _builder_db_path() -> Path:
    override = os.environ.get("KITTY_BUILDER_DATA_DIR")
    if override:
        return Path(override) / "builder_queue.db"
    return repo_root() / "data" / "kittybuilder" / "builder_queue.db"


def _status_snapshot() -> dict[str, Any]:
    return build_status_snapshot_readonly(db_path=_builder_db_path())


def kitty_context() -> dict[str, Any]:
    """Return Kitty's existing cold-start receipt without reinterpreting it."""
    try:
        raw = build_context_receipt(repo_root())
    except Exception as exc:
        return receipt(
            "kitty_context",
            ok=False,
            state="unavailable",
            error_code="context_unavailable",
            error=f"{type(exc).__name__}: {exc}",
            next_action="Repair the cold-start/context receipt before acting on the repository.",
            context=None,
        )
    return receipt(
        "kitty_context",
        ok=bool(raw.get("ok")),
        state="ready" if raw.get("ok") else "attention",
        next_action=raw.get("next_action"),
        context=raw,
    )


def _find_work(
    snapshot: dict[str, Any],
    *,
    mission_id: str | None,
    task_id: str | None,
) -> tuple[dict[str, Any] | None, str | None]:
    initiatives = snapshot.get("initiatives") or []
    if task_id:
        for initiative in initiatives:
            if mission_id and initiative.get("initiative_id") != mission_id:
                continue
            for packet in initiative.get("packets") or []:
                if packet.get("task_id") == task_id:
                    return packet, packet.get("task_state")
        return None, None
    if mission_id:
        for initiative in initiatives:
            if initiative.get("initiative_id") == mission_id:
                return initiative, initiative.get("state")
        return None, None
    return snapshot, "available"


def work_status(
    mission_id: str | None = None,
    task_id: str | None = None,
) -> dict[str, Any]:
    """Read the current durable Builder projection through a non-mutating DB view."""
    try:
        snapshot = _status_snapshot()
    except Exception as exc:
        return receipt(
            "work_status",
            ok=False,
            state="unavailable",
            error_code="builder_unavailable",
            error=f"{type(exc).__name__}: {exc}",
            next_action="Restore or initialize Builder through its supported operator path.",
            work=None,
        )
    work, state = _find_work(snapshot, mission_id=mission_id, task_id=task_id)
    if work is None:
        requested = task_id or mission_id or "requested work"
        return receipt(
            "work_status",
            ok=False,
            state="unknown",
            error_code="work_not_found",
            error=f"Builder work not found: {requested}",
            next_action="Check the exact durable mission/task identifier.",
            work=None,
        )
    return receipt(
        "work_status",
        ok=True,
        state=state,
        next_action=(work.get("projection") or {}).get("next_action")
        if isinstance(work, dict)
        else None,
        work=work,
        integrity=snapshot.get("integrity"),
    )


def _latest_attempt(packet: dict[str, Any]) -> dict[str, Any] | None:
    history = packet.get("attempt_history") or []
    return history[0] if history else None


def work_result(
    mission_id: str | None = None,
    task_id: str | None = None,
) -> dict[str, Any]:
    """Return durable result evidence; narration alone can never mark work done."""
    status_result = work_status(mission_id=mission_id, task_id=task_id)
    if not status_result.get("ok"):
        status_result["operation"] = "work_result"
        return status_result
    work = status_result["work"]
    if task_id or (isinstance(work, dict) and "task_id" in work):
        packet = work
        task_state = packet.get("task_state")
        result = {
            "mission_id": packet.get("initiative_id"),
            "packet_id": packet.get("packet_id"),
            "task_id": packet.get("task_id"),
            "task_state": task_state,
            "complete": task_state == "done",
            "attempt": _latest_attempt(packet),
            "publication": packet.get("publication"),
            "blocker": packet.get("blocked_reason") or packet.get("last_error"),
        }
        return receipt(
            "work_result",
            ok=True,
            state=task_state,
            next_action=(packet.get("projection") or {}).get("next_action"),
            result=result,
        )

    initiative = work
    packets = initiative.get("packets") or []
    return receipt(
        "work_result",
        ok=True,
        state=initiative.get("state"),
        next_action=initiative.get("next_packet"),
        result={
            "mission_id": initiative.get("initiative_id"),
            "complete": initiative.get("state") == "completed",
            "packets": [
                {
                    "packet_id": packet.get("packet_id"),
                    "task_id": packet.get("task_id"),
                    "task_state": packet.get("task_state"),
                    "attempt": _latest_attempt(packet),
                    "publication": packet.get("publication"),
                }
                for packet in packets
            ],
        },
    )


def _artifact_refs(
    initiative: dict[str, Any] | None,
) -> tuple[dict[str, str], list[dict[str, str]]]:
    unknowns: list[dict[str, str]] = []
    refs: dict[str, str] = {}
    manifest = (initiative or {}).get("manifest") or {}
    description = manifest.get("description")
    if isinstance(description, str) and MCP_ARTIFACT_MARKER in description:
        payload = description.split(MCP_ARTIFACT_MARKER, 1)[1].strip()
        try:
            decoded = json.loads(payload)
            if isinstance(decoded, dict):
                refs = {str(k): str(v) for k, v in decoded.items() if v is not None}
        except json.JSONDecodeError:
            unknowns.append(
                {"field": "artifacts", "reason": "MCP artifact linkage is malformed"}
            )
    if not refs.get("design_path") or not refs.get("design_sha"):
        unknowns.append(
            {
                "field": "artifacts.design",
                "reason": "no approved design artifact linkage recorded",
            }
        )
    if not refs.get("plan_path") or not refs.get("plan_sha"):
        unknowns.append(
            {
                "field": "artifacts.plan",
                "reason": "no approved implementation plan linkage recorded",
            }
        )
    return refs, unknowns


def _select_current_packet(work: dict[str, Any]) -> dict[str, Any] | None:
    packets = work.get("packets") or []
    next_packet = work.get("next_packet")
    if next_packet:
        for packet in packets:
            if packet.get("packet_id") == next_packet:
                return packet
    for packet in packets:
        if packet.get("task_state") != "done":
            return packet
    return packets[-1] if packets else None


def resume_context(
    mission_id: str | None = None,
    task_id: str | None = None,
) -> dict[str, Any]:
    """Build a compact durable handoff that does not depend on chat history."""
    kitty = kitty_context()
    status_result = work_status(mission_id=mission_id, task_id=task_id)
    if not status_result.get("ok"):
        status_result["operation"] = "resume_context"
        return status_result

    work = status_result["work"]
    resolved_mission = (
        work.get("initiative_id")
        if isinstance(work, dict) and work.get("initiative_id")
        else mission_id
    )
    if not resolved_mission:
        return receipt(
            "resume_context",
            ok=False,
            state="needs_decision",
            error_code="mission_required",
            error="resume_context requires a durable mission/task identifier",
            next_action="Supply the Builder mission or task ID to resume.",
        )

    try:
        initiative = get_initiative(resolved_mission, db_path=_builder_db_path())
    except Exception as exc:
        initiative = None
        initiative_error = f"{type(exc).__name__}: {exc}"
    else:
        initiative_error = None

    if "task_id" in work:
        current = work
        initiative_work = None
        mission_status = work_status(mission_id=resolved_mission)
        if mission_status.get("ok"):
            initiative_work = mission_status.get("work")
    else:
        initiative_work = work
        current = _select_current_packet(work)

    refs, linkage_unknowns = _artifact_refs(initiative)
    raw_context = kitty.get("context") or {}
    git = raw_context.get("git") or {}
    base_sha = refs.get("base_sha") or (current or {}).get("base_sha")
    latest = _latest_attempt(current or {})
    publication = (current or {}).get("publication") or None
    blocker = (
        (current or {}).get("blocked_reason")
        or (current or {}).get("last_error")
        or (initiative_work or {}).get("pause_reason")
    )
    next_action = ((current or {}).get("projection") or {}).get("next_action")
    if not next_action:
        next_action = (
            (initiative_work or {}).get("next_packet")
            or status_result.get("next_action")
            or kitty.get("next_action")
            or "Inspect work_status and resolve any unknowns before continuing."
        )

    unknowns = list(raw_context.get("unknowns") or []) + linkage_unknowns
    if initiative_error:
        unknowns.append({"field": "initiative", "reason": initiative_error})

    objective = (current or {}).get("objective")
    if not objective and initiative:
        packets = ((initiative.get("manifest") or {}).get("packets") or [])
        if packets:
            objective = packets[0].get("objective")

    pr = None
    if publication:
        pr = {
            "number": publication.get("pr_number"),
            "url": publication.get("pr_url"),
            "head_sha": publication.get("head_sha"),
            "checks_state": publication.get("checks_state"),
            "review_state": publication.get("review_state"),
            "merged": publication.get("merged"),
        }

    cold_start_ok = bool(kitty.get("ok"))
    state = (
        (current or {}).get("task_state")
        or (initiative_work or {}).get("state")
        or status_result.get("state")
    )
    if not cold_start_ok:
        state = "attention"

    return receipt(
        "resume_context",
        ok=cold_start_ok,
        state=state,
        error_code=None if cold_start_ok else "context_attention",
        error=None
        if cold_start_ok
        else kitty.get("error")
        or "Kitty cold-start receipt is not trusted; continuity needs attention.",
        next_action=next_action,
        objective=objective,
        artifacts={
            "design": (
                {"path": refs["design_path"], "sha": refs["design_sha"]}
                if refs.get("design_path") and refs.get("design_sha")
                else None
            ),
            "plan": (
                {"path": refs["plan_path"], "sha": refs["plan_sha"]}
                if refs.get("plan_path") and refs.get("plan_sha")
                else None
            ),
        },
        repository={
            "base_sha": base_sha,
            "current_sha": git.get("head"),
            "branch": git.get("branch"),
        },
        mission={
            "id": resolved_mission,
            "manifest_sha256": (initiative or {}).get("manifest_sha256"),
            "state": (initiative_work or {}).get("state"),
        },
        execution_owner="builder" if current and current.get("task_id") else None,
        current_work={
            "packet_id": (current or {}).get("packet_id"),
            "task_id": (current or {}).get("task_id"),
            "state": (current or {}).get("task_state"),
            "attempt_count": (current or {}).get("attempt_count"),
        },
        evidence={
            "implementation": (latest or {}).get("implementation"),
            "validation": (latest or {}).get("validation"),
            "review": (latest or {}).get("review"),
        },
        pr=pr,
        blocker=blocker,
        unknowns=unknowns,
        sources={
            "kitty": "gateway.context_receipt.build_context_receipt",
            "builder": "gateway.builder_status_readonly.build_status_snapshot_readonly",
            "initiative": "gateway.builder_status_readonly.get_initiative_readonly",
        },
    )
