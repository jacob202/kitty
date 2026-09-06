"""Bounded Mission Supervisor context and cycle contract."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Callable

from gateway import agent_workspace, automation_actions, memory_mission

DecisionFn = Callable[[dict[str, Any]], dict[str, Any]]
DelegateFn = Callable[[dict[str, Any]], dict[str, Any]]
NotifyFn = Callable[[dict[str, Any]], Any]
ObserveFn = Callable[[dict[str, Any]], list[dict[str, Any]]]
BuilderResumeFn = Callable[..., dict[str, Any]]
_ALLOWED_OUTCOMES = {"advance", "needs_jacob", "blocked", "verify", "no_change"}
_NO_EXPECTATION = object()


def read_builder_projection(
    mission_id: str,
    *,
    db_path: Path = memory_mission.MISSION_DB_FILE,
    resume: BuilderResumeFn | None = None,
) -> dict[str, Any]:
    """Re-read Builder-owned execution truth through its canonical resume seam.

    Gateway Mission state owns only the durable Builder locator. The returned
    projection is intentionally not persisted into Mission state, so Builder
    remains the sole owner of queue, attempt, execution, review, and
    publication truth.
    """
    mission = memory_mission.get_mission(mission_id, db_path=db_path)
    locator = mission.get("builder_locator")
    if not isinstance(locator, dict):
        return {"locator": None, "builder": None}

    initiative_id = locator.get("initiative_id")
    if not isinstance(initiative_id, str) or not initiative_id:
        raise memory_mission.MissionError("Mission has an invalid Builder initiative locator")

    if resume is None:
        from gateway import conversation_handoff

        resume = conversation_handoff.resume
    builder = resume(mission_id=initiative_id, task_id=None)
    if not isinstance(builder, dict):
        raise memory_mission.MissionError("Builder resume returned an invalid projection")
    projected_mission = builder.get("mission")
    if builder.get("ok") is True and (
        not isinstance(projected_mission, dict)
        or projected_mission.get("id") != initiative_id
    ):
        raise memory_mission.MissionError(
            "Builder projection resolved a different Builder initiative"
        )
    return {"locator": dict(locator), "builder": builder}


def _observation_key(observation: dict[str, Any]) -> str:
    source = observation.get("source")
    locator = observation.get("locator")
    digest = observation.get("digest")
    values = (source, locator, digest)
    if not all(isinstance(value, str) and value.strip() for value in values):
        raise memory_mission.MissionError(
            "source observations require source, locator, and digest"
        )
    return f"{source}|{locator}"


def _changed_observations(
    mission: dict[str, Any], observations: list[dict[str, Any]]
) -> tuple[dict[str, str], list[dict[str, Any]]]:
    cursors = dict(mission["source_cursors"])
    changed: list[dict[str, Any]] = []
    for observation in observations:
        key = _observation_key(observation)
        if cursors.get(key) != observation["digest"]:
            changed.append(dict(observation))
        cursors[key] = observation["digest"]
    return cursors, changed


def _persist(
    mission_id: str, *, supervisor_id: str, supervisor_epoch: int,
    cursors: dict[str, str], cycle: dict[str, Any],
    pending_escalation: dict[str, Any] | None, db_path: Path,
    expected_last_cycle: dict[str, Any] | None | object = _NO_EXPECTATION,
) -> None:
    kwargs: dict[str, Any] = {}
    if expected_last_cycle is not _NO_EXPECTATION:
        kwargs["expected_last_cycle"] = expected_last_cycle
    memory_mission.record_cycle(
        mission_id,
        supervisor_id=supervisor_id,
        supervisor_epoch=supervisor_epoch,
        source_cursors=cursors,
        cycle=cycle,
        pending_escalation=pending_escalation,
        db_path=db_path,
        **kwargs,
    )


def run_cycle(
    mission_id: str, *, supervisor_id: str, supervisor_epoch: int,
    observations: list[dict[str, Any]], decide: DecisionFn,
    delegate: DelegateFn | None = None, notify: NotifyFn | None = None,
    db_path: Path = memory_mission.MISSION_DB_FILE,
) -> dict[str, Any]:
    mission = memory_mission.assert_supervisor(
        mission_id,
        supervisor_id=supervisor_id,
        supervisor_epoch=supervisor_epoch,
        db_path=db_path,
    )
    if mission["status"] == "PAUSED":
        return {
            "outcome": "paused",
            "reason": mission.get("status_reason") or "Mission is paused",
        }
    if mission["status"] == "STOPPED":
        return {
            "outcome": "stopped",
            "reason": mission.get("status_reason") or "Mission is stopped",
        }
    if mission["status"] != "EXECUTING":
        raise memory_mission.MissionError(
            f"Mission cycle requires EXECUTING state, got {mission['status']}"
        )

    previous_cycle = mission.get("last_cycle")
    if isinstance(previous_cycle, dict) and previous_cycle.get("delegation_state") in {
        "pending",
        "unknown",
    }:
        return {
            "outcome": "blocked",
            "reason": "previous delegation outcome is unresolved; reconcile its receipt before retrying",
            "delegation_state": previous_cycle["delegation_state"],
            "task": previous_cycle.get("task"),
        }

    cursors, changed = _changed_observations(mission, observations)
    cycle: dict[str, Any]
    if not changed:
        cycle = {
            "outcome": "no_change",
            "reason": "no source observation changed",
            "changed": [],
        }
        _persist(
            mission_id, supervisor_id=supervisor_id,
            supervisor_epoch=supervisor_epoch, cursors=cursors, cycle=cycle,
            pending_escalation=mission["pending_escalation"], db_path=db_path,
            expected_last_cycle=previous_cycle,
        )
        return cycle

    decision = decide({"mission": mission, "changed_observations": changed})
    if not isinstance(decision, dict) or decision.get("outcome") not in _ALLOWED_OUTCOMES:
        raise memory_mission.MissionError("Supervisor decision has an invalid outcome")

    cycle = {**decision, "changed": changed}
    pending_escalation = mission["pending_escalation"]
    expected_last_cycle_for_final: dict[str, Any] | None = previous_cycle
    if decision["outcome"] == "advance":
        task = decision.get("task")
        if not isinstance(task, dict) or delegate is None:
            cycle = {
                "outcome": "blocked",
                "reason": "no supported executor is available for the proposed advance",
                "changed": changed,
            }
        else:
            cycle["delegation_state"] = "pending"
            _persist(
                mission_id, supervisor_id=supervisor_id,
                supervisor_epoch=supervisor_epoch, cursors=cursors, cycle=cycle,
                pending_escalation=pending_escalation, db_path=db_path,
                expected_last_cycle=previous_cycle,
            )
            expected_last_cycle_for_final = dict(cycle)
            try:
                delegation = delegate(task)
            except Exception as exc:
                cycle["outcome"] = "blocked"
                cycle["reason"] = (
                    "delegation outcome is unknown; reconcile its receipt before retrying"
                )
                cycle["delegation_state"] = "unknown"
                cycle["delegation_error"] = f"{type(exc).__name__}: {exc}"
                _persist(
                    mission_id, supervisor_id=supervisor_id,
                    supervisor_epoch=supervisor_epoch, cursors=cursors, cycle=cycle,
                    pending_escalation=pending_escalation, db_path=db_path,
                    expected_last_cycle=expected_last_cycle_for_final,
                )
                return cycle
            cycle["delegation"] = delegation
            if not isinstance(delegation, dict) or not delegation.get("ok"):
                cycle["outcome"] = "blocked"
                cycle["reason"] = (
                    "delegation did not produce a successful execution receipt; reconcile before retrying"
                )
                cycle["delegation_state"] = "unknown"
            else:
                cycle["delegation_state"] = "completed"

    if decision["outcome"] == "needs_jacob":
        key = decision.get("escalation_key")
        if not isinstance(key, str) or not key.strip():
            raise memory_mission.MissionError(
                "needs_jacob decisions require an escalation_key"
            )

        same_pending = bool(
            pending_escalation and pending_escalation.get("key") == key
        )
        cycle["notified"] = False
        if not same_pending:
            pending_escalation = {
                "key": key,
                "reason": str(
                    decision.get("reason") or "Jacob input is required"
                ),
                "notification_state": "pending",
            }
            # Persist the decision before any attention side effect.
            _persist(
                mission_id, supervisor_id=supervisor_id,
                supervisor_epoch=supervisor_epoch, cursors=cursors, cycle=cycle,
                pending_escalation=pending_escalation, db_path=db_path,
                expected_last_cycle=previous_cycle,
            )
            expected_last_cycle_for_final = dict(cycle)
            if notify is not None:
                try:
                    notify(dict(pending_escalation))
                except Exception as exc:
                    cycle["notification_error"] = f"{type(exc).__name__}: {exc}"
                else:
                    cycle["notified"] = True
                    memory_mission.record_notification_delivery(
                        mission_id,
                        escalation_key=key,
                        expected_pending_escalation=pending_escalation,
                        expected_last_cycle=expected_last_cycle_for_final,
                        delivered_cycle=cycle,
                        db_path=db_path,
                    )
                    return cycle

    _persist(
        mission_id, supervisor_id=supervisor_id,
        supervisor_epoch=supervisor_epoch, cursors=cursors, cycle=cycle,
        pending_escalation=pending_escalation, db_path=db_path,
        expected_last_cycle=expected_last_cycle_for_final,
    )
    return cycle




def reconcile_delegation(
    mission_id: str, *, supervisor_id: str, supervisor_epoch: int,
    outcome: str, evidence_locator: str,
    db_path: Path = memory_mission.MISSION_DB_FILE,
) -> dict[str, Any]:
    """Resolve one pending/unknown delegation from external evidence.

    This does not execute work. It records whether the prior effect is now
    proven complete or proven not to have happened, so recovery can continue
    without guessing or changing task identity.
    """
    mission = memory_mission.assert_supervisor(
        mission_id, supervisor_id=supervisor_id, supervisor_epoch=supervisor_epoch,
        db_path=db_path,
    )
    if mission["status"] != "EXECUTING":
        raise memory_mission.MissionError("delegation reconciliation requires EXECUTING state")
    previous = mission.get("last_cycle")
    if not isinstance(previous, dict) or previous.get("delegation_state") not in {
        "pending", "unknown",
    }:
        raise memory_mission.MissionError("Mission has no unresolved delegation to reconcile")
    if outcome not in {"completed", "failed_no_effect"}:
        raise memory_mission.MissionError(
            "delegation reconciliation outcome must be completed or failed_no_effect"
        )
    if not isinstance(evidence_locator, str) or not evidence_locator.strip():
        raise memory_mission.MissionError("delegation reconciliation requires evidence_locator")
    task = previous.get("task")
    if not isinstance(task, dict) or not isinstance(task.get("id"), str) or not task["id"].strip():
        raise memory_mission.MissionError("unresolved delegation has no stable task identity")

    cycle = dict(previous)
    prior_error = cycle.pop("delegation_error", None)
    cycle.pop("delegation", None)
    cycle["delegation_reconciliation"] = {
        "outcome": outcome,
        "evidence_locator": evidence_locator.strip(),
        "prior_error": prior_error,
    }
    if outcome == "completed":
        cycle["outcome"] = "advance"
        cycle["delegation_state"] = "completed"
        cycle["reason"] = "delegation effect was independently reconciled as completed"
    else:
        cycle["outcome"] = "blocked"
        cycle["delegation_state"] = "retryable"
        cycle["reason"] = (
            "delegation was independently reconciled as no effect; "
            "a replacement worker may continue the same task"
        )
    _persist(
        mission_id, supervisor_id=supervisor_id, supervisor_epoch=supervisor_epoch,
        cursors=dict(mission["source_cursors"]), cycle=cycle,
        pending_escalation=mission["pending_escalation"], db_path=db_path,
        expected_last_cycle=previous,
    )
    return cycle


def replace_delegation_worker(
    mission_id: str, *, supervisor_id: str, supervisor_epoch: int,
    replacement_task: dict[str, Any], delegate: DelegateFn,
    db_path: Path = memory_mission.MISSION_DB_FILE,
) -> dict[str, Any]:
    """Retry a proven-no-effect delegation with a replacement worker only."""
    mission = memory_mission.assert_supervisor(
        mission_id, supervisor_id=supervisor_id, supervisor_epoch=supervisor_epoch,
        db_path=db_path,
    )
    if mission["status"] != "EXECUTING":
        raise memory_mission.MissionError("worker replacement requires EXECUTING state")
    previous = mission.get("last_cycle")
    if not isinstance(previous, dict) or previous.get("delegation_state") != "retryable":
        raise memory_mission.MissionError("Mission delegation is not retryable")
    prior_task = previous.get("task")
    if not isinstance(prior_task, dict):
        raise memory_mission.MissionError("retryable delegation has no task")
    prior_task_id = prior_task.get("id")
    replacement_task_id = replacement_task.get("id") if isinstance(replacement_task, dict) else None
    if not isinstance(prior_task_id, str) or not prior_task_id.strip():
        raise memory_mission.MissionError("retryable delegation has no stable task identity")
    if replacement_task_id != prior_task_id:
        raise memory_mission.MissionError("replacement worker must preserve task identity")
    worker_id = replacement_task.get("worker_id")
    if not isinstance(worker_id, str) or not worker_id.strip():
        raise memory_mission.MissionError("replacement task requires worker_id")
    if worker_id == prior_task.get("worker_id"):
        raise memory_mission.MissionError("replacement worker must differ from the failed worker")

    cycle = dict(previous)
    cycle.pop("delegation", None)
    cycle.pop("delegation_error", None)
    cycle["outcome"] = "advance"
    cycle["reason"] = "replacement worker continuing verified task identity"
    cycle["task"] = dict(replacement_task)
    cycle["delegation_state"] = "pending"
    cycle["replacement_of"] = {
        "task_id": prior_task_id,
        "worker_id": prior_task.get("worker_id"),
        "reconciliation": previous.get("delegation_reconciliation"),
    }
    cursors = dict(mission["source_cursors"] )
    _persist(
        mission_id, supervisor_id=supervisor_id, supervisor_epoch=supervisor_epoch,
        cursors=cursors, cycle=cycle, pending_escalation=mission["pending_escalation"],
        db_path=db_path, expected_last_cycle=previous,
    )
    pending_cycle = dict(cycle)
    try:
        delegation = delegate(dict(replacement_task))
    except Exception as exc:
        cycle["outcome"] = "blocked"
        cycle["reason"] = "replacement delegation outcome is unknown; reconcile before retrying"
        cycle["delegation_state"] = "unknown"
        cycle["delegation_error"] = f"{type(exc).__name__}: {exc}"
        _persist(
            mission_id, supervisor_id=supervisor_id, supervisor_epoch=supervisor_epoch,
            cursors=cursors, cycle=cycle,
            pending_escalation=mission["pending_escalation"], db_path=db_path,
            expected_last_cycle=pending_cycle,
        )
        return cycle
    cycle["delegation"] = delegation
    if not isinstance(delegation, dict) or not delegation.get("ok"):
        cycle["outcome"] = "blocked"
        cycle["reason"] = "replacement delegation did not produce a successful receipt"
        cycle["delegation_state"] = "unknown"
    else:
        cycle["delegation_state"] = "completed"
    _persist(
        mission_id, supervisor_id=supervisor_id, supervisor_epoch=supervisor_epoch,
        cursors=cursors, cycle=cycle, pending_escalation=mission["pending_escalation"],
        db_path=db_path, expected_last_cycle=pending_cycle,
    )
    return cycle


def observe_global_thread(message_id: str) -> dict[str, Any]:
    """Return a bounded change observation for one explicit GAR thread locator.

    GAR remains the owner of message content. Mission state receives only a
    locator, digest, and small provenance metadata so collaboration evidence
    cannot silently become Mission truth or a copied transcript.
    """
    try:
        rows = agent_workspace.list_thread(message_id, limit=500)
    except agent_workspace.AgentWorkspaceError as exc:
        raise automation_actions.SourceUnavailable(
            f"workspace_global thread {message_id!r} is unavailable: {exc}"
        ) from exc
    if not rows:
        raise automation_actions.SourceUnavailable(
            f"workspace_global thread {message_id!r} returned no messages"
        )
    if len(rows) >= 500:
        raise automation_actions.SourceUnavailable(
            f"workspace_global thread {message_id!r} reached the observation cap; "
            "freshness cannot be proven"
        )

    digest_rows = [
        {
            "id": row.get("id"),
            "parent_message_id": row.get("parent_message_id"),
            "sender_kind": row.get("sender_kind"),
            "sender_id": row.get("sender_id"),
            "recipient_id": row.get("recipient_id"),
            "message_kind": row.get("message_kind"),
            "content": row.get("content"),
            "created_at": row.get("created_at"),
        }
        for row in rows
    ]
    encoded = json.dumps(digest_rows, sort_keys=True, separators=(",", ":")).encode()
    root_id = str(rows[0]["id"])
    last = rows[-1]
    return {
        "source": "workspace_global",
        "locator": f"thread:{root_id}",
        "digest": hashlib.sha256(encoded).hexdigest(),
        "observed_at": float(last["created_at"]),
        "classification": "collaboration_evidence",
        "message_count": len(rows),
        "last_message_id": str(last["id"]),
    }

def build_automation_action(
    mission_id: str, *, observe: ObserveFn, decide: DecisionFn,
    delegate: DelegateFn | None = None, notify: NotifyFn | None = None,
    db_path: Path = memory_mission.MISSION_DB_FILE,
) -> automation_actions.ActionCallable:
    """Adapt one Mission cycle to Kitty's existing Automation action contract."""

    async def action(payload: dict[str, Any]) -> automation_actions.ActionResult:
        mission = memory_mission.get_mission(mission_id, db_path=db_path)
        if mission["status"] != "EXECUTING":
            return automation_actions.ActionResult(
                status="condition_false",
                result_pointer=f"mission:{mission_id}",
                error=f"Mission is {mission['status']}",
            )

        observations = observe(payload)
        cycle = run_cycle(
            mission_id,
            supervisor_id=mission["supervisor"]["id"],
            supervisor_epoch=mission["supervisor"]["epoch"],
            observations=observations,
            decide=decide,
            delegate=delegate,
            notify=notify,
            db_path=db_path,
        )
        cycle_outcome = cycle["outcome"]
        if cycle_outcome in {"no_change", "paused", "stopped"}:
            return automation_actions.ActionResult(
                status="condition_false",
                result_pointer=f"mission:{mission_id}",
                error=(
                    str(cycle.get("reason"))
                    if cycle_outcome in {"paused", "stopped"}
                    else None
                ),
            )
        return automation_actions.ActionResult(
            status="completed", result_pointer=f"mission:{mission_id}"
        )

    return action
