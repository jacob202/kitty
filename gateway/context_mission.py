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
_ALLOWED_OUTCOMES = {"advance", "needs_jacob", "blocked", "verify", "no_change"}


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
) -> None:
    memory_mission.record_cycle(
        mission_id,
        supervisor_id=supervisor_id,
        supervisor_epoch=supervisor_epoch,
        source_cursors=cursors,
        cycle=cycle,
        pending_escalation=pending_escalation,
        db_path=db_path,
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
        )
        return cycle

    decision = decide({"mission": mission, "changed_observations": changed})
    if not isinstance(decision, dict) or decision.get("outcome") not in _ALLOWED_OUTCOMES:
        raise memory_mission.MissionError("Supervisor decision has an invalid outcome")

    cycle = {**decision, "changed": changed}
    pending_escalation = mission["pending_escalation"]
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
            )
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
            )
            if notify is not None:
                try:
                    notify(dict(pending_escalation))
                except Exception as exc:
                    cycle["notification_error"] = f"{type(exc).__name__}: {exc}"
                else:
                    pending_escalation["notification_state"] = "delivered"
                    cycle["notified"] = True

    _persist(
        mission_id, supervisor_id=supervisor_id,
        supervisor_epoch=supervisor_epoch, cursors=cursors, cycle=cycle,
        pending_escalation=pending_escalation, db_path=db_path,
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
        status = "condition_false" if cycle["outcome"] == "no_change" else "completed"
        return automation_actions.ActionResult(
            status=status, result_pointer=f"mission:{mission_id}"
        )

    return action
