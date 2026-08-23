"""One named Automation action registry and execution path.

Time, signal, monitor, and manual triggers all dispatch through this module.
Authorization is delegated to the existing action_grants policy engine; callers
cannot supply their own tier or approval outcome.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from gateway import action_grants, automation_runs

VALID_TRIGGER_KINDS = frozenset({"time", "signal", "monitor", "manual"})
ACTION_RESULT_STATUSES = frozenset({"completed", "source_unavailable", "condition_false"})


class AutomationActionError(RuntimeError):
    """Base error for Automation action registration/execution."""


class SourceUnavailable(AutomationActionError):
    """An action could not run because its source/integration is unavailable."""


class ConditionFalse(AutomationActionError):
    """The trigger occurred but the action condition did not match."""


@dataclass(frozen=True)
class ActionPolicy:
    capability: str
    tier: str = "T0"
    scope_type: str = "global"
    scope_id: str = ""
    session_id: str | None = None
    estimated_cost_usd: float | None = None


@dataclass(frozen=True)
class ActionResult:
    status: str = "completed"
    result_pointer: str | None = None
    error: str | None = None


ActionCallable = Callable[[dict[str, Any]], Any | Awaitable[Any]]


@dataclass(frozen=True)
class ActionDefinition:
    fn: ActionCallable
    policy: ActionPolicy


_registry: dict[str, ActionDefinition] = {}


def register_action(
    name: str,
    fn: ActionCallable,
    *,
    policy: ActionPolicy | None = None,
) -> None:
    """Register one server-owned action definition."""
    if not name or not name.strip():
        raise AutomationActionError("action name is required")
    resolved_policy = policy or ActionPolicy(capability=name, tier="T0")
    if resolved_policy.tier not in {"T0", "T1", "T2"}:
        raise AutomationActionError(f"invalid action tier {resolved_policy.tier!r}")
    _registry[name] = ActionDefinition(fn=fn, policy=resolved_policy)


def clear_registry() -> None:
    """Clear in-process registrations; primarily used by isolated tests."""
    _registry.clear()


def get_actions() -> list[str]:
    return sorted(_registry)


def get_definition(name: str) -> ActionDefinition | None:
    return _registry.get(name)


def _policy_evidence(
    policy: ActionPolicy,
    *,
    scope_type: str | None = None,
    scope_id: str | None = None,
) -> tuple[dict[str, Any], action_grants.Decision]:
    resolved_scope_type = scope_type or policy.scope_type
    resolved_scope_id = policy.scope_id if scope_id is None else scope_id
    decision = action_grants.evaluate(
        capability=policy.capability,
        tier=policy.tier,
        status="proposed",
        scope_type=resolved_scope_type,
        scope_id=resolved_scope_id,
        session_id=policy.session_id,
        estimated_cost_usd=policy.estimated_cost_usd,
    )
    evidence = {
        "capability": policy.capability,
        "tier": policy.tier,
        "scope_type": resolved_scope_type,
        "scope_id": resolved_scope_id,
        "session_id": policy.session_id,
        "estimated_cost_usd": policy.estimated_cost_usd,
        "outcome": decision.outcome,
        "basis": decision.basis,
        "reason": decision.reason,
        "grant_id": decision.grant_id,
    }
    return evidence, decision


async def _invoke(fn: ActionCallable, payload: dict[str, Any]) -> Any:
    result = fn(payload)
    if inspect.isawaitable(result):
        return await result
    return result


def _normalize_result(value: Any) -> ActionResult:
    if value is None:
        return ActionResult()
    if isinstance(value, ActionResult):
        if value.status not in ACTION_RESULT_STATUSES:
            raise AutomationActionError(f"invalid action result status {value.status!r}")
        return value
    return ActionResult()


async def run_action(
    name: str,
    *,
    trigger_kind: str,
    automation_id: str,
    trigger_ref: str | None = None,
    schedule_id: str | None = None,
    payload: dict[str, Any] | None = None,
    run_id: str | None = None,
    policy_scope_type: str | None = None,
    policy_scope_id: str | None = None,
) -> dict[str, Any]:
    """Execute one registered action and return its durable run evidence."""
    if trigger_kind not in VALID_TRIGGER_KINDS:
        raise AutomationActionError(f"invalid trigger kind {trigger_kind!r}")
    payload = payload or {}

    if run_id is None:
        run = automation_runs.begin_run(
            automation_id=automation_id,
            action=name,
            trigger_kind=trigger_kind,
            trigger_ref=trigger_ref,
            schedule_id=schedule_id,
        )
    else:
        existing_run = automation_runs.get_run(run_id)
        if existing_run is None:
            raise AutomationActionError(f"run {run_id!r} does not exist")
        run = existing_run
        if run["status"] != "running":
            raise AutomationActionError(f"run {run_id!r} is not running")
        if run["action"] != name:
            raise AutomationActionError(
                f"run {run_id!r} belongs to {run['action']!r}, not {name!r}"
            )

    definition = _registry.get(name)
    if definition is None:
        return automation_runs.finish_run(
            run["id"],
            status="action_unavailable",
            error=f"registered action {name!r} is not registered",
        )

    policy_evidence, decision = _policy_evidence(
        definition.policy,
        scope_type=policy_scope_type,
        scope_id=policy_scope_id,
    )
    if decision.outcome != "allow":
        return automation_runs.finish_run(
            run["id"],
            status="policy_refused",
            error=decision.reason,
            policy=policy_evidence,
        )

    try:
        raw_result = await _invoke(definition.fn, payload)
        result = _normalize_result(raw_result)
    except SourceUnavailable as exc:
        return automation_runs.finish_run(
            run["id"],
            status="source_unavailable",
            error=str(exc),
            policy=policy_evidence,
        )
    except ConditionFalse as exc:
        return automation_runs.finish_run(
            run["id"],
            status="condition_false",
            error=str(exc),
            policy=policy_evidence,
        )
    except Exception as exc:
        return automation_runs.finish_run(
            run["id"],
            status="failed",
            error=f"{type(exc).__name__}: {exc}",
            policy=policy_evidence,
        )

    return automation_runs.finish_run(
        run["id"],
        status=result.status,
        result_pointer=result.result_pointer,
        error=result.error,
        policy=policy_evidence,
    )
