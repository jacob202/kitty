"""Bounded Mission Supervisor context and cycle contract."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from gateway import memory_mission

DecisionFn = Callable[[dict[str, Any]], dict[str, Any]]
DelegateFn = Callable[[dict[str, Any]], dict[str, Any]]
NotifyFn = Callable[[dict[str, Any]], Any]
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
            delegation = delegate(task)
            cycle["delegation"] = delegation
            if not isinstance(delegation, dict) or not delegation.get("ok"):
                cycle["outcome"] = "blocked"
                cycle["reason"] = (
                    "delegation did not produce a successful execution receipt"
                )

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
