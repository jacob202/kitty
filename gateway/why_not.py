"""Truthful "Why didn't this happen?" explanations for automations.

QoL Packet 03: eliminate silent failure. Every meaningful automation/action can
answer why it did not run — including non-execution. This module is a pure,
read-only resolution surface that composes existing evidence only:

- ``cron`` schedule state (enabled / due / next occurrence),
- the #550 Automation Run ledger (``automation_runs``) for claimed and terminal
  outcomes,
- ``action_grants`` for the manual-action approval story,
- the supervisor for the execution-gap story (cron runner alive or not).

Nothing here writes to any store. "Nothing happened" is never represented by
absence of evidence when the system can know why.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any

from gateway import action_grants, automation_actions, automation_runs, cron
from gateway.automation_supervisor import supervisor

# Ledger terminal statuses mapped to the packet outcome vocabulary. Each is its
# own truthful answer; the ledger is the single evidence source for them.
_RUN_STATUS_TO_OUTCOME = {
    "completed": "completed",
    "failed": "failed",
    "interrupted": "interrupted",
    "action_unavailable": "action_unavailable",
    "source_unavailable": "source_unavailable",
    "condition_false": "condition_false",
    "policy_refused": "policy_refused",
}


class WhyNotFound(KeyError):
    """No schedule with the supplied id exists."""


@dataclass(frozen=True)
class Explanation:
    """The packet's explanation shape: Status, Reason, Relevant timestamp,
    Action, Automation, Evidence, Next step."""

    status: str
    reason: str
    relevant_at: float | None = None
    action: str | None = None
    automation: str | None = None
    evidence: dict[str, Any] = field(default_factory=dict)
    next_step: str = ""


def _run_evidence(run: dict[str, Any]) -> dict[str, Any]:
    return {
        "run_id": run.get("id"),
        "run_status": run.get("status"),
        "trigger_kind": run.get("trigger_kind"),
        "due_at": run.get("due_at"),
        "started_at": run.get("started_at"),
        "completed_at": run.get("completed_at"),
        "error": run.get("error"),
        "result_pointer": run.get("result_pointer"),
        "policy": run.get("policy"),
    }


def _terminal_reason(run: dict[str, Any]) -> str:
    status = run["status"]
    if status == "completed":
        return "the automation ran successfully"
    if status == "failed":
        return f"execution failed: {run.get('error') or 'no error recorded'}"
    if status == "interrupted":
        return (
            "execution was interrupted: "
            f"{run.get('error') or 'the gateway restarted before completion'}"
        )
    if status == "action_unavailable":
        return f"the action could not run: {run.get('error') or 'action is not registered'}"
    if status == "source_unavailable":
        return f"the source was unavailable: {run.get('error') or 'source unavailable'}"
    if status == "condition_false":
        return f"the trigger condition was false: {run.get('error') or 'condition did not match'}"
    if status == "policy_refused":
        return f"policy refused the action: {run.get('error') or 'not authorized'}"
    return f"the run ended with status {status}"


def _terminal_next_step(outcome: str) -> str:
    if outcome == "completed":
        return "nothing to do; the automation already ran"
    if outcome == "failed":
        return "fix the recorded error; the next occurrence will retry"
    if outcome == "interrupted":
        return "the gateway restarted mid-run; the next occurrence will retry"
    if outcome == "action_unavailable":
        return "register the action or fix its registration"
    if outcome == "source_unavailable":
        return "restore the source; the next occurrence will retry"
    if outcome == "condition_false":
        return "nothing to do unless the condition changes"
    if outcome == "policy_refused":
        return "approve or grant the capability so the action can run"
    return "review the run evidence"


def _explain_run(run: dict[str, Any], *, action: str, automation_id: str) -> Explanation:
    if run["status"] == "running":
        return Explanation(
            status="claimed",
            reason="the occurrence was already claimed and is executing now",
            relevant_at=run.get("started_at"),
            action=action,
            automation=automation_id,
            evidence=_run_evidence(run),
            next_step="wait for the running execution to finish",
        )
    outcome = _RUN_STATUS_TO_OUTCOME.get(run["status"], run["status"])
    return Explanation(
        status=outcome,
        reason=_terminal_reason(run),
        relevant_at=run.get("completed_at") or run.get("started_at"),
        action=action,
        automation=automation_id,
        evidence=_run_evidence(run),
        next_step=_terminal_next_step(outcome),
    )


def _next_due_at(schedule: dict[str, Any], now: float) -> float | None:
    """Timestamp of the next occurrence, or ``None`` when unknown/none remains."""
    last_run = float(schedule.get("last_run") or 0.0)
    s_type = schedule.get("schedule_type", "")
    s_value = schedule.get("schedule_value", "")

    if s_type == "interval":
        try:
            interval = float(s_value) * 60
        except (TypeError, ValueError):
            return None
        if interval <= 0:
            return None
        if last_run <= 0:
            return now
        return last_run + interval

    if s_type == "daily":
        try:
            import datetime
            from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

            parts = s_value.split(":")
            target_h, target_m = int(parts[0]), int(parts[1])
            raw_metadata = schedule.get("metadata") or {}
            metadata = json.loads(raw_metadata) if isinstance(raw_metadata, str) else raw_metadata
            timezone_name = metadata.get("timezone") if isinstance(metadata, dict) else None
            if timezone_name:
                try:
                    zone = ZoneInfo(str(timezone_name))
                except ZoneInfoNotFoundError:
                    return None
                local_now = datetime.datetime.fromtimestamp(now, zone)
            else:
                local_now = datetime.datetime.fromtimestamp(now)
            candidate = local_now.replace(
                hour=target_h, minute=target_m, second=0, microsecond=0
            )
            if candidate.timestamp() <= now:
                candidate = candidate + datetime.timedelta(days=1)
            return candidate.timestamp()
        except (TypeError, ValueError, IndexError, json.JSONDecodeError):
            return None

    if s_type == "once":
        try:
            import datetime

            target = datetime.datetime.fromisoformat(s_value).timestamp()
            if target > now and float(schedule.get("last_run") or 0.0) == 0:
                return target
            return None
        except (ValueError, TypeError):
            return None

    return None


def _explain_schedule_row(row: dict[str, Any], *, now: float) -> Explanation:
    action = str(row.get("action") or "")
    schedule_id = str(row["id"])
    runs = automation_runs.list_runs(automation_id=schedule_id, limit=5)
    last_run_ts = float(row.get("last_run") or 0.0)

    state = cron.explain_schedule(row, now=now)
    schedule_state = state["state"]

    if schedule_state == "disabled":
        return Explanation(
            status="disabled",
            reason="schedule is disabled",
            action=action,
            automation=schedule_id,
            evidence={"schedule_state": "disabled"},
            next_step="enable the schedule to allow it to run",
        )

    if schedule_state == "not_due":
        # The schedule is genuinely not due. But if the last occurrence left a
        # non-successful run behind, that is the failure the user is really
        # asking about — surface it instead of hiding it behind "not due yet".
        last_occurrence_run = next(
            (
                r
                for r in runs
                if r.get("due_at") is not None and float(r["due_at"]) >= last_run_ts - 1.0
            ),
            None,
        )
        if last_occurrence_run is not None and last_occurrence_run["status"] != "completed":
            return _explain_run(last_occurrence_run, action=action, automation_id=schedule_id)
        next_due = _next_due_at(row, now)
        return Explanation(
            status="not_due",
            reason="next occurrence is not due yet",
            relevant_at=next_due,
            action=action,
            automation=schedule_id,
            evidence={"schedule_state": "not_due", "next_due_at": next_due},
            next_step="wait until the next occurrence is due",
        )

    due_at = float(state["due_at"])
    current_run = next(
        (
            r
            for r in runs
            if r.get("due_at") is not None and float(r["due_at"]) == due_at
        ),
        None,
    )
    if current_run is None:
        current_run = next(
            (
                r
                for r in runs
                if r.get("started_at") is not None and float(r["started_at"]) >= due_at
            ),
            None,
        )
    if current_run is not None:
        return _explain_run(current_run, action=action, automation_id=schedule_id)

    # Due, enabled, and no run recorded for this occurrence: the execution gap.
    # The supervisor is the evidence of whether cron could have claimed it.
    cron_status = supervisor.get_status("cron")
    if cron_status["status"] != "available":
        return Explanation(
            status="execution_gap",
            reason=(
                f"scheduled occurrence was due at {due_at:.0f} but no automation run "
                "was recorded for it; the cron supervisor is not running"
            ),
            relevant_at=due_at,
            action=action,
            automation=schedule_id,
            evidence={
                "schedule_state": "due",
                "due_at": due_at,
                "supervisor": cron_status,
            },
            next_step="investigate why the cron runner did not claim the occurrence",
        )
    return Explanation(
        status="pending_claim",
        reason="the scheduled occurrence is due and waiting for the running cron supervisor to claim it",
        relevant_at=due_at,
        action=action,
        automation=schedule_id,
        evidence={
            "schedule_state": "due",
            "due_at": due_at,
            "supervisor": cron_status,
        },
        next_step="no action needed; the runner claims due occurrences on its next cycle",
    )


def explain_schedule(schedule_id: str, *, now: float | None = None) -> Explanation:
    """Explain one cron schedule: why it has or has not run."""
    current = time.time() if now is None else float(now)
    row = next((s for s in cron.list_schedules() if s["id"] == schedule_id), None)
    if row is None:
        raise WhyNotFound(f"schedule not found: {schedule_id}")
    return _explain_schedule_row(row, now=current)


def _grant_state(
    capability: str, *, now: float
) -> tuple[str | None, dict[str, Any] | None]:
    """Whether the newest grant for a capability is dead, and how.

    Returns (None, grant) when the newest grant is still active; the caller then
    falls back to the evaluate() outcome for the operative reason.
    """
    grants = action_grants.list_grants(capability=capability, include_inactive=True, limit=1)
    if not grants:
        return None, None
    grant = grants[0]
    if grant["revoked_at"] is not None:
        return "revoked", grant
    if grant["expires_at"] is not None and float(grant["expires_at"]) <= now:
        return "expired", grant
    return None, grant


def _explain_manual_action(
    action: str, definition: automation_actions.ActionDefinition, *, now: float
) -> Explanation:
    policy = definition.policy
    decision = action_grants.evaluate(
        capability=policy.capability,
        tier=policy.tier,
        status="proposed",
        scope_type=policy.scope_type,
        scope_id=policy.scope_id,
        session_id=policy.session_id,
        estimated_cost_usd=policy.estimated_cost_usd,
        now=now,
    )
    grant_evidence = {
        "capability": policy.capability,
        "tier": policy.tier,
        "scope_type": policy.scope_type,
        "scope_id": policy.scope_id,
        "decision": decision.outcome,
        "basis": decision.basis,
        "reason": decision.reason,
        "grant_id": decision.grant_id,
    }

    if decision.outcome == "deny":
        return Explanation(
            status="policy_refused",
            reason=decision.reason,
            action=action,
            evidence=grant_evidence,
            next_step="the capability is denied for this scope; only a scoped allow can change that",
        )

    grant_state, grant = _grant_state(policy.capability, now=now)
    if grant_state == "expired" and grant is not None:
        return Explanation(
            status="grant_expired",
            reason=f"the standing grant for {policy.capability!r} expired",
            relevant_at=grant["expires_at"],
            action=action,
            evidence={**grant_evidence, "grant_id": grant["id"], "expires_at": grant["expires_at"]},
            next_step="create a new grant; the previous one expired",
        )
    if grant_state == "revoked" and grant is not None:
        return Explanation(
            status="grant_revoked",
            reason=f"the standing grant for {policy.capability!r} was revoked",
            relevant_at=grant["revoked_at"],
            action=action,
            evidence={**grant_evidence, "grant_id": grant["id"], "revoked_at": grant["revoked_at"]},
            next_step="create a new grant; the previous one was revoked",
        )
    if decision.outcome == "ask":
        return Explanation(
            status="approval_required",
            reason=decision.reason,
            action=action,
            evidence=grant_evidence,
            next_step="approve the action or create a standing grant for it",
        )

    runs = automation_runs.list_runs(action=action, limit=1)
    if not runs:
        return Explanation(
            status="not_triggered",
            reason=f"action {action!r} is authorized but has never been triggered",
            action=action,
            evidence={**grant_evidence, "registered": True},
            next_step=f"trigger it via POST /automations/actions/{action}/run",
        )
    run = runs[0]
    return _explain_run(run, action=action, automation_id=str(run.get("automation_id") or ""))


def explain_action(action: str, *, now: float | None = None) -> Explanation:
    """Explain an action by name: schedule-backed or manual.

    A schedule-backed action reports its schedule's truth first. A manual-only
    action resolves approval state, then the last durable run.
    """
    current = time.time() if now is None else float(now)
    schedules = [s for s in cron.list_schedules() if s.get("action") == action]
    if schedules:
        return _explain_schedule_row(schedules[0], now=current)
    definition = automation_actions.get_definition(action)
    if definition is None:
        return Explanation(
            status="action_unavailable",
            reason=f"action {action!r} is not registered",
            action=action,
            evidence={"registered": False},
            next_step="register the action or fix its registration",
        )
    return _explain_manual_action(action, definition, now=current)
