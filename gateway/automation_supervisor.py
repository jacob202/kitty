"""Central lifecycle/status seam for Gateway background services."""

from __future__ import annotations

import asyncio
import inspect
import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

VALID_STATUSES = {
    "available",
    "degraded",
    "stale",
    "unavailable",
    "unknown",
}

StopCallable = Callable[[], Any | Awaitable[Any]]


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
        return {
            "name": name,
            "status": status,
            "reason": reason,
            "updated_at": service.updated_at,
            "last_heartbeat": service.last_heartbeat,
            "stale_after": service.stale_after,
        }

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
