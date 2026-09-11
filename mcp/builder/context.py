"""Read-only Kitty/Builder projections for conversational MCP clients."""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any

from gateway.builder_status_readonly import (
    build_status_snapshot_readonly,
)
from gateway.builder_status_readonly import (
    get_initiative_readonly as get_initiative,
)
from gateway.context_receipt import build_context_receipt

from .repo_tools import repo_root
from .schemas import MCP_ARTIFACT_MARKER, receipt


def _builder_db_path() -> Path:
    # mission_approve() -> bi.apply_manifest() writes through
    # gateway.builder_queue.BUILDER_QUEUE_DB (see that module's own default in
    # gateway/paths.py: KITTY_BUILDER_DATA_DIR -> KITTY_DATA_ROOT -> the
    # canonical checkout). This used to reimplement its own resolution here,
    # independently, and only checked KITTY_BUILDER_DATA_DIR before falling
    # straight to a hardcoded repo-relative path -- skipping the KITTY_DATA_ROOT
    # tier entirely. A caller that isolates a run with just KITTY_DATA_ROOT (the
    # acceptance-testing default -- see docs/contracts/PC-BUILDER.md) got a
    # reader pointed at the canonical checkout while the writer used the
    # isolated root, so resume/status reads of a freshly approved job failed
    # as "unavailable". Reading the live module attribute (not a frozen
    # import) also means this agrees with a test/operator override of
    # gateway.builder_queue.BUILDER_QUEUE_DB itself, not just the env vars.
    override = os.environ.get("KITTY_BUILDER_DATA_DIR")
    if override:
        return Path(override) / "builder_queue.db"
    import gateway.builder_queue as _builder_queue

    return _builder_queue.BUILDER_QUEUE_DB


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


ACCEPTANCE_NONE = "none"
ACCEPTANCE_UNAVAILABLE = "unavailable"


def _mission_acceptance(
    initiative_id: str | None,
    *,
    expect_binding: bool = False,
    expected_task_id: str | None = None,
) -> dict[str, Any]:
    """Report the outcome-acceptance fact, separately from Builder's task.

    Three answers, deliberately distinct:

    - a state from the bound Mission (``unreviewed`` / ``accepted`` / ...);
    - ``none`` — no Mission is bound to direct Builder work, so acceptance
      does not apply to it;
    - ``unavailable`` with a binding error — a conversation-backed job was
      expected to have a Gateway Mission, but that durable binding is missing;
    - ``unavailable`` — the Mission store could not be read. That is an outage
      with a cause, not the same statement as "there is nothing recorded", and
      it is reported with the error rather than swallowed.

    Never reports ``accepted`` without having read it.
    """
    if not initiative_id:
        return {
            "state": ACCEPTANCE_NONE,
            "reviewer_id": None,
            "mission_id": None,
            "error": None,
        }
    try:
        from gateway import memory_mission

        mission = memory_mission.mission_for_initiative(initiative_id)
    except Exception as exc:
        # An existing but not-yet-initialized application database is also a
        # legitimate pre-Mission state for direct MCP work. Restrict this to
        # SQLite's exact missing-table failure; corrupt, locked, and unreadable
        # stores must remain explicit outages.
        cause = exc.__cause__
        absent_store = (
            isinstance(exc, memory_mission.MissionError)
            and cause is None
            and str(exc).endswith(" does not exist")
        )
        missing_schema = (
            isinstance(cause, sqlite3.OperationalError)
            and str(cause) == "no such table: missions"
        )
        if not expect_binding and (absent_store or missing_schema):
            return {
                "state": ACCEPTANCE_NONE,
                "reviewer_id": None,
                "mission_id": None,
                "error": None,
            }
        return {
            "state": ACCEPTANCE_UNAVAILABLE,
            "reviewer_id": None,
            "mission_id": None,
            "error": f"{type(exc).__name__}: {exc}",
        }
    if mission is None:
        if expect_binding:
            return {
                "state": ACCEPTANCE_UNAVAILABLE,
                "reviewer_id": None,
                "mission_id": None,
                "error": (
                    "Expected Gateway Mission binding is missing for Builder "
                    f"initiative {initiative_id}"
                ),
            }
        return {
            "state": ACCEPTANCE_NONE,
            "reviewer_id": None,
            "mission_id": None,
            "error": None,
        }
    # A Mission bound only to the initiative is not a resolved Builder binding.
    # bind_builder_locator records the initiative at proposal time and adds the
    # durable Builder task id only once approval returns one, so a locator with
    # no task id means the binding is still missing — not that acceptance simply
    # was not recorded. Resolving it here would let a resume report a partial
    # binding as complete and discard the only replayable approval checkpoint.
    # The message keeps the "binding ... missing" shape callers match on so a
    # partial or mismatched binding is still reported as recoverable.
    if expect_binding:
        bound_task_id = (mission.get("builder_locator") or {}).get("task_id")
        mismatch = bool(expected_task_id) and bound_task_id != expected_task_id
        if not isinstance(bound_task_id, str) or not bound_task_id or mismatch:
            detail = (
                f"bound task {bound_task_id!r} does not match {expected_task_id!r}"
                if mismatch
                else "no Builder task is bound"
            )
            return {
                "state": ACCEPTANCE_UNAVAILABLE,
                "reviewer_id": None,
                "mission_id": None,
                "error": (
                    "Expected Gateway Mission binding is missing for Builder "
                    f"initiative {initiative_id} ({detail})"
                ),
            }

    acceptance = mission.get("acceptance") or {}
    return {
        "state": acceptance.get("state") or ACCEPTANCE_NONE,
        "reviewer_id": acceptance.get("reviewer_id"),
        "mission_id": mission.get("mission_id"),
        "error": None,
    }


def _awaiting_acceptance(
    *, builder_done: bool, acceptance: dict[str, Any]
) -> tuple[bool, str | None]:
    """Say whether finished Builder work is still waiting on an outcome decision.

    Deliberately *not* folded into ``complete``. Nothing in production records
    an acceptance today, so gating ``complete`` on it would make that field
    permanently false — trading a claim that overstates progress for one that
    can never be satisfied. Instead the two facts are reported side by side and
    the caller says the true sentence: Builder finished, nobody has accepted
    the outcome yet.
    """
    if not builder_done:
        return False, None
    state = acceptance.get("state")
    if state == "accepted":
        return False, None
    if state == ACCEPTANCE_UNAVAILABLE:
        return True, acceptance.get("error") or (
            "the Mission store could not be read to confirm acceptance"
        )
    if state == ACCEPTANCE_NONE:
        return False, None
    return True, f"the Mission outcome is {state}, not accepted"


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
        initiative_id = packet.get("initiative_id")
        acceptance = _mission_acceptance(initiative_id)
        builder_done = task_state == "done"
        awaiting, awaiting_because = _awaiting_acceptance(
            builder_done=builder_done, acceptance=acceptance
        )
        result = {
            "mission_id": initiative_id,
            "packet_id": packet.get("packet_id"),
            "task_id": packet.get("task_id"),
            "task_state": task_state,
            # `complete` keeps its established meaning: Builder finished its
            # task. Outcome acceptance is the separate fact beside it.
            "complete": builder_done,
            "builder_task_complete": builder_done,
            "mission_acceptance": acceptance,
            "awaiting_acceptance": awaiting,
            "awaiting_acceptance_because": awaiting_because,
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
    initiative_id = initiative.get("initiative_id")
    acceptance = _mission_acceptance(initiative_id)
    builder_done = initiative.get("state") == "completed"
    awaiting, awaiting_because = _awaiting_acceptance(
        builder_done=builder_done, acceptance=acceptance
    )
    return receipt(
        "work_result",
        ok=True,
        state=initiative.get("state"),
        next_action=initiative.get("next_packet"),
        result={
            "mission_id": initiative_id,
            "complete": builder_done,
            "builder_task_complete": builder_done,
            "mission_acceptance": acceptance,
            "awaiting_acceptance": awaiting,
            "awaiting_acceptance_because": awaiting_because,
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
    *,
    expect_mission_binding: bool = False,
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

    initiative_error: str | None = None
    try:
        initiative = get_initiative(resolved_mission, db_path=_builder_db_path())
    except Exception as exc:
        initiative = None
        initiative_error = f"{type(exc).__name__}: {exc}"

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
    # Read Builder's own terminal fact before the cold-start receipt is allowed
    # to overwrite `state` with "attention". Whether Builder finished its task
    # is durable and has nothing to do with whether this session's context
    # receipt is trusted; deriving it from the overwritten value would report a
    # finished task as unfinished because of an unrelated failure.
    builder_done = (
        (current or {}).get("task_state") == "done"
        or (initiative_work or {}).get("state") == "completed"
    )
    state = (
        (current or {}).get("task_state")
        or (initiative_work or {}).get("state")
        or status_result.get("state")
    )
    if not cold_start_ok:
        state = "attention"

    # This is the projection Chat reopens a job through. Without acceptance
    # here, Builder's terminal state is the only thing Chat can show, and it
    # gets presented as the finished user outcome.
    acceptance = (
        _mission_acceptance(
            resolved_mission,
            expect_binding=True,
            # The duty is on the resolver to prove the binding is complete, so
            # hand it the Builder task this resume is actually about.
            expected_task_id=(current or {}).get("task_id"),
        )
        if expect_mission_binding
        else _mission_acceptance(resolved_mission)
    )
    awaiting, awaiting_because = _awaiting_acceptance(
        builder_done=builder_done, acceptance=acceptance
    )
    if awaiting and awaiting_because:
        unknowns.append({"field": "outcome_acceptance", "reason": awaiting_because})

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
        builder_task_complete=builder_done,
        mission_acceptance=acceptance,
        awaiting_acceptance=awaiting,
        awaiting_acceptance_because=awaiting_because,
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
