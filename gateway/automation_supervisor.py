"""Central lifecycle/status seam for Gateway background services.

Packet 05 (QoL) adds supervised self-recovery: a recoverable service is
launched through a factory and, on a retryable failure, restarted with bounded
exponential backoff up to a retry budget. Recovery produces evidence and never
silently restarts forever; a permanent failure or an exhausted budget lands the
service in ``degraded`` with a cooldown instead of an invisible restart loop.
"""

from __future__ import annotations

import asyncio
import inspect
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

VALID_STATUSES = {
    "available",
    "degraded",
    "stale",
    "unavailable",
    "unknown",
}

StopCallable = Callable[[], Any | Awaitable[Any]]
ServiceFactory = Callable[[], Any | Awaitable[Any] | None]


@dataclass(frozen=True)
class RecoveryPolicy:
    """Bounded, classified restart policy for a supervised background service.

    On each retryable failure the service is relaunched after a backoff of
    ``backoff_seconds * backoff_factor ** (attempt - 1)`` seconds, capped at
    ``backoff_max``. After ``max_attempts`` failed launches the service is left
    ``degraded`` for at least ``cooldown_seconds`` instead of being restarted
    forever. An error is retryable unless it matches ``non_retryable_errors``;
    when ``retryable_errors`` is non-empty only those types are retryable.
    """

    max_attempts: int = 3
    backoff_seconds: float = 2.0
    backoff_factor: float = 5.0
    backoff_max: float = 60.0
    retryable_errors: tuple[type[BaseException], ...] = ()
    non_retryable_errors: tuple[type[BaseException], ...] = ()
    cooldown_seconds: float = 300.0


def backoff_for(policy: RecoveryPolicy, attempt: int) -> float:
    """Backoff (seconds) to wait after the given failed launch attempt."""
    return min(policy.backoff_max, policy.backoff_seconds * (policy.backoff_factor ** (attempt - 1)))


@dataclass
class _Service:
    name: str
    status: str = "unknown"
    reason: str = "not started"
    updated_at: float = 0.0
    last_heartbeat: float | None = None
    stale_after: float | None = None
    task: Any = None
    stop: StopCallable | None = None
    policy: RecoveryPolicy | None = None
    current: Any = None
    cooldown_until: float | None = None
    recovery_events: list[dict[str, Any]] = field(default_factory=list)


class AutomationSupervisor:
    def __init__(self) -> None:
        self._services: dict[str, _Service] = {}

    def mark(
        self,
        name: str,
        status: str,
        *,
        reason: str,
        stale_after: float | None = None,
    ) -> None:
        if status not in VALID_STATUSES:
            raise ValueError(f"invalid supervisor status {status!r}")
        now = time.time()
        service = self._services.setdefault(name, _Service(name=name))
        service.status = status
        service.reason = reason
        service.updated_at = now
        if stale_after is not None:
            service.stale_after = stale_after
        if status == "available" and service.last_heartbeat is None:
            service.last_heartbeat = now

    def heartbeat(self, name: str) -> None:
        now = time.time()
        service = self._services.setdefault(name, _Service(name=name))
        service.last_heartbeat = now
        service.updated_at = now

    def track_task(
        self,
        name: str,
        task: Any,
        *,
        stop: StopCallable | None = None,
        stale_after: float | None = None,
    ) -> None:
        if task is None:
            self.mark(name, "unavailable", reason="service did not start")
            return
        service = self._services.setdefault(name, _Service(name=name))
        service.task = task
        service.stop = stop
        service.stale_after = stale_after
        self.mark(name, "available", reason="task running", stale_after=stale_after)

        def _done(done_task: Any) -> None:
            if done_task.cancelled():
                self.mark(name, "unavailable", reason="task stopped")
                return
            exc = done_task.exception()
            if exc is not None:
                self.mark(name, "degraded", reason=f"{type(exc).__name__}: {exc}")
            else:
                self.mark(name, "unavailable", reason="task exited")

        task.add_done_callback(_done)

    def track_recoverable(
        self,
        name: str,
        factory: ServiceFactory,
        *,
        policy: RecoveryPolicy,
        stop: StopCallable | None = None,
        stale_after: float | None = None,
    ) -> None:
        """Supervise a background service launched through ``factory``.

        The factory is (re)invoked after every retryable failure so it must
        return a fresh coroutine/task (or ``None`` when the service declines to
        start). The supervisor loop itself is the registered ``task`` so
        ``stop_all`` cancels the service through it.
        """
        service = self._services.setdefault(name, _Service(name=name))
        service.policy = policy
        service.stop = stop
        service.stale_after = stale_after
        service.recovery_events = []
        service.cooldown_until = None
        service.current = None
        self.mark(name, "unknown", reason="recovery supervising", stale_after=stale_after)
        service.task = asyncio.create_task(self._recovery_loop(name, factory, policy))

    async def _recovery_loop(
        self,
        name: str,
        factory: ServiceFactory,
        policy: RecoveryPolicy,
    ) -> None:
        service = self._services[name]
        attempt = 0
        while True:
            attempt += 1
            try:
                started = factory()
            except asyncio.CancelledError:
                raise
            except BaseException as exc:
                if not self._recover_from(name, attempt, exc, policy, factory_failed=True):
                    return
                continue
            if started is None:
                self.mark(name, "unavailable", reason="service did not start")
                return
            task = started if asyncio.isfuture(started) else asyncio.ensure_future(started)
            service.current = task
            self.mark(name, "available", reason="task running", stale_after=service.stale_after)
            try:
                await task
            except asyncio.CancelledError:
                if not task.done():
                    task.cancel()
                self.mark(name, "unavailable", reason="task stopped")
                return
            except BaseException as exc:
                if not self._recover_from(name, attempt, exc, policy, factory_failed=False):
                    return
                continue
            else:
                self.mark(name, "unavailable", reason="task exited")
                return

    def _recover_from(
        self,
        name: str,
        attempt: int,
        exc: BaseException,
        policy: RecoveryPolicy,
        *,
        factory_failed: bool,
    ) -> bool:
        """Record recovery evidence and return True when a retry should run."""
        service = self._services[name]
        retryable = self._is_retryable(exc, policy)
        budget = attempt < policy.max_attempts
        exhausted = retryable and not budget
        outcome = "retrying" if retryable and budget else ("exhausted" if exhausted else "stopped")
        backoff = backoff_for(policy, attempt) if retryable and budget else 0.0
        service.recovery_events.append(
            {
                "attempt": attempt,
                "error": f"{type(exc).__name__}: {exc}",
                "error_type": type(exc).__name__,
                "retryable": retryable,
                "backoff": backoff,
                "outcome": outcome,
                "recorded_at": time.time(),
            }
        )
        if retryable and budget:
            self.mark(
                name,
                "degraded",
                reason=f"recovery attempt {attempt}/{policy.max_attempts}: {type(exc).__name__}: {exc}",
            )
            return True
        service.cooldown_until = time.time() + policy.cooldown_seconds
        if exhausted:
            self.mark(
                name,
                "degraded",
                reason=(
                    f"recovery exhausted after {policy.max_attempts} attempts: "
                    f"{type(exc).__name__}: {exc}"
                ),
            )
        else:
            self.mark(name, "degraded", reason=f"non-retryable failure: {type(exc).__name__}: {exc}")
        return False

    @staticmethod
    def _is_retryable(exc: BaseException, policy: RecoveryPolicy) -> bool:
        if isinstance(exc, asyncio.CancelledError):
            return False
        if any(isinstance(exc, t) for t in policy.non_retryable_errors):
            return False
        if policy.retryable_errors:
            return any(isinstance(exc, t) for t in policy.retryable_errors)
        return True

    def get_status(self, name: str) -> dict[str, Any]:
        service = self._services.get(name) or _Service(name=name)
        status = service.status
        reason = service.reason
        if (
            status == "available"
            and service.stale_after is not None
            and service.last_heartbeat is not None
            and time.time() - service.last_heartbeat > service.stale_after
        ):
            status = "stale"
            reason = "service heartbeat is stale"
        recovery: dict[str, Any] | None = None
        if service.policy is not None:
            recovery = {
                "enabled": True,
                "max_attempts": service.policy.max_attempts,
                "attempts": len(service.recovery_events),
                "backoff_seconds": service.policy.backoff_seconds,
                "backoff_max": service.policy.backoff_max,
                "cooldown_until": service.cooldown_until,
                "events": list(service.recovery_events),
            }
        return {
            "name": name,
            "status": status,
            "reason": reason,
            "updated_at": service.updated_at,
            "last_heartbeat": service.last_heartbeat,
            "stale_after": service.stale_after,
            "recovery": recovery,
        }

    def recovery_evidence(self, name: str) -> list[dict[str, Any]]:
        service = self._services.get(name)
        if service is None:
            return []
        return list(service.recovery_events)

    def snapshot(self) -> list[dict[str, Any]]:
        return [self.get_status(name) for name in sorted(self._services)]

    async def stop_all(self) -> None:
        for name, service in list(self._services.items())[::-1]:
            try:
                if service.stop is not None:
                    result = service.stop()
                    if inspect.isawaitable(result):
                        await result
                elif service.task is not None and not service.task.done():
                    service.task.cancel()
                    try:
                        await service.task
                    except asyncio.CancelledError:
                        pass
            except Exception as exc:
                self.mark(
                    name,
                    "degraded",
                    reason=f"shutdown failed: {type(exc).__name__}: {exc}",
                )
                continue
            self.mark(name, "unavailable", reason="stopped by Gateway shutdown")


supervisor = AutomationSupervisor()
