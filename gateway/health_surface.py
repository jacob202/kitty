"""Kitty Health surface — read-only projection answering "is Kitty working?".

Composes existing lifecycle/readiness primitives (automation supervisor,
cron, image provider probes, image jobs, memory probe, grant store) into a
single glanceable snapshot. Does NOT introduce a second health database and
does NOT mutate any source of truth.

The supervisor status vocabulary is reused verbatim:
``available / degraded / stale / unavailable / unknown``.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

logger = logging.getLogger("kitty.health_surface")

# Statuses that mean "needs attention" for overall/degraded derivation.
_PROBLEM_STATUSES = frozenset({"degraded", "stale", "unavailable", "unknown"})


@dataclass
class HealthDomain:
    """One domain's truthful lifecycle state for the projection."""

    name: str
    status: str
    reason: str = ""
    detail: dict[str, Any] = field(default_factory=dict)


HealthSource = Callable[[], Awaitable[HealthDomain]]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# --- Default sources (compose existing primitives; nothing invented) --------


async def _gateway_source() -> HealthDomain:
    """Gateway is serving (this projection is served by it); LiteLLM is the
    real dependency, probed exactly like GET /health does."""
    from gateway.http_client import get_http_client
    from gateway.paths import LITELLM_BASE

    litellm_reachable = False
    try:
        client = await get_http_client()
        resp = await client.get(f"{LITELLM_BASE}/health/readiness", timeout=1.5)
        litellm_reachable = resp.status_code == 200
    except Exception:  # noqa: BLE001 — any failure means "not reachable"
        logger.warning("health surface: LiteLLM unreachable")
    if litellm_reachable:
        return HealthDomain(
            "gateway", "available", reason="gateway serving; LiteLLM reachable",
            detail={"litellm_reachable": True},
        )
    return HealthDomain(
        "gateway", "degraded", reason="LiteLLM unreachable; gateway still serving",
        detail={"litellm_reachable": False},
    )


async def _database_source() -> HealthDomain:
    from gateway import db as kitty_db
    from gateway.paths import KITTY_DB_FILE

    try:
        with kitty_db.connect(KITTY_DB_FILE) as conn:
            conn.execute("SELECT 1").fetchone()
    except Exception as exc:  # noqa: BLE001
        return HealthDomain(
            "database", "unavailable",
            reason=f"sqlite open/query failed: {type(exc).__name__}: {exc}",
        )
    return HealthDomain("database", "available", reason="sqlite reachable")


async def _memory_source() -> HealthDomain:
    from gateway import memory

    try:
        memory._probe_memory_backend()
    except Exception as exc:  # noqa: BLE001 — the probe reports every config failure mode
        return HealthDomain(
            "memory", "degraded",
            reason=(
                f"semantic memory unavailable: {exc}; "
                "explicit memory remains available independently"
            ),
        )
    return HealthDomain("memory", "available", reason="semantic memory available")


async def _supervisor_source() -> HealthDomain:
    from gateway.automation_supervisor import supervisor

    # Fail loud: a snapshot that raises must never collapse into "green".
    snapshot = supervisor.snapshot()
    if not snapshot:
        return HealthDomain(
            "automation_supervisor", "unknown",
            reason="no tracked services",
            detail={"services": []},
        )
    worst = _worst_status(s["status"] for s in snapshot)
    unhealthy = [s["name"] for s in snapshot if s["status"] in _PROBLEM_STATUSES]
    return HealthDomain(
        "automation_supervisor",
        worst,
        reason=(
            f"{len(unhealthy)} tracked service(s) need attention: {', '.join(unhealthy)}"
            if unhealthy
            else f"{len(snapshot)} tracked service(s) available"
        ),
        detail={"services": snapshot},
    )


async def _cron_source() -> HealthDomain:
    from gateway import cron
    from gateway.automation_supervisor import supervisor

    status = supervisor.get_status("cron")
    schedule_count = 0
    try:
        schedule_count = len(cron.list_schedules())
    except Exception as exc:  # noqa: BLE001
        logger.warning("health surface: cron schedule list failed: %s", exc)
    return HealthDomain(
        "cron",
        status["status"],
        reason=status["reason"],
        detail={"schedules": schedule_count},
    )


async def _telegram_source() -> HealthDomain:
    from gateway.automation_supervisor import supervisor

    status = supervisor.get_status("telegram")
    return HealthDomain("telegram", status["status"], reason=status["reason"])


async def _image_lab_source() -> HealthDomain:
    from gateway.automation_supervisor import supervisor

    entries = {
        name: supervisor.get_status(name)
        for name in ("image-recovery", "image-batch-worker")
    }
    if not entries:
        return HealthDomain("image_lab", "unknown", reason="no image workers tracked")
    worst = _worst_status(s["status"] for s in entries.values())
    return HealthDomain(
        "image_lab",
        worst,
        reason="; ".join(f"{name}: {s['status']}" for name, s in entries.items()),
        detail={name: s["status"] for name, s in entries.items()},
    )


async def _image_providers_source() -> HealthDomain:
    from gateway import image_runner

    probes = {
        "airforce": image_runner.airforce_images_available,
        "fal": image_runner.fal_images_available,
        "openrouter": image_runner.openrouter_images_available,
        "flux": image_runner.flux_images_available,
        "flux2": image_runner.flux2_images_available,
    }
    results: dict[str, tuple[bool, str]] = {}
    outcomes = await asyncio.gather(
        *[asyncio.to_thread(probe) for probe in probes.values()]
    )
    for name, (ok, reason) in zip(probes, outcomes):
        results[name] = (ok, reason)

    available = [name for name, (ok, _) in results.items() if ok]
    if available:
        return HealthDomain(
            "image_providers",
            "available",
            reason=f"{len(available)}/{len(results)} provider(s) ready",
            detail={name: {"ok": ok, "reason": reason} for name, (ok, reason) in results.items()},
        )
    reasons = [f"{name}: {reason}" for name, (ok, reason) in results.items() if reason]
    return HealthDomain(
        "image_providers",
        "unavailable",
        reason="; ".join(reasons) if reasons else "no image provider available",
        detail={name: {"ok": False, "reason": reason} for name, (_, reason) in results.items()},
    )


async def _image_queue_source() -> HealthDomain:
    from gateway.image_jobs import ImageJobError, list_queue, list_unknown

    try:
        queued = len(list_queue())
        unknown = len(list_unknown())
    except ImageJobError as exc:
        return HealthDomain(
            "image_queue", "degraded",
            reason=f"queue read failed: {exc}",
        )
    if unknown:
        return HealthDomain(
            "image_queue", "degraded",
            reason=f"{unknown} job(s) with unresolved provider outcome need recovery",
            detail={"queued": queued, "unknown": unknown},
        )
    return HealthDomain(
        "image_queue", "available",
        reason=f"{queued} job(s) in flight" if queued else "queue empty",
        detail={"queued": queued, "unknown": 0},
    )


async def _ollama_source() -> HealthDomain:
    import httpx

    base_url = "http://localhost:11434"
    try:
        resp = await asyncio.to_thread(
            httpx.get, f"{base_url}/api/tags", timeout=2.0,
        )
        if resp.status_code < 400:
            return HealthDomain("ollama", "available", reason="embedding runtime reachable")
        return HealthDomain(
            "ollama", "unavailable",
            reason=f"embedding runtime returned HTTP {resp.status_code}",
        )
    except Exception as exc:  # noqa: BLE001
        return HealthDomain(
            "ollama", "unavailable",
            reason=(
                f"embedding runtime unreachable at {base_url}: "
                f"{type(exc).__name__}; explicit memory remains available independently"
            ),
        )


async def _pending_grants_source() -> HealthDomain:
    from gateway import action_grants

    try:
        grants = action_grants.list_grants(include_inactive=False)
    except Exception as exc:  # noqa: BLE001
        return HealthDomain(
            "pending_grants", "unavailable",
            reason=f"grant store read failed: {type(exc).__name__}: {exc}",
            detail={"count": 0},
        )
    return HealthDomain(
        "pending_grants",
        "available",
        reason=f"{len(grants)} active grant(s)" if grants else "no active grants",
        detail={"count": len(grants)},
    )


def _worst_status(statuses) -> str:
    """Return the most-severe supervisor status from an iterable.

    Order: available < degraded < stale < unavailable < unknown.
    """
    severity = {
        "available": 0,
        "degraded": 1,
        "stale": 2,
        "unavailable": 3,
        "unknown": 4,
    }
    worst = "available"
    worst_sev = -1
    for status in statuses:
        sev = severity.get(status, 4)
        if sev > worst_sev:
            worst_sev = sev
            worst = status
    return worst


def default_sources() -> dict[str, HealthSource]:
    return {
        "gateway": _gateway_source,
        "database": _database_source,
        "memory": _memory_source,
        "automation_supervisor": _supervisor_source,
        "cron": _cron_source,
        "telegram": _telegram_source,
        "image_lab": _image_lab_source,
        "image_providers": _image_providers_source,
        "image_queue": _image_queue_source,
        "ollama": _ollama_source,
        "pending_grants": _pending_grants_source,
    }


# --- Projection -------------------------------------------------------------


async def build_health_surface(
    sources: dict[str, HealthSource] | None = None,
) -> dict[str, Any]:
    """Build the KittyHealth snapshot from the given (or default) domain sources.

    Sources are awaited in order; an exception from any source propagates —
    the projection never silently reports green on a broken subsystem.
    """
    if sources is None:
        sources = default_sources()

    domains: list[HealthDomain] = []
    for name, source in sources.items():
        domain = await source()
        if domain.status not in {
            "available", "degraded", "stale", "unavailable", "unknown",
        }:
            raise ValueError(f"domain {name!r} reported invalid status {domain.status!r}")
        domains.append(domain)

    degraded = [d for d in domains if d.status in _PROBLEM_STATUSES]
    still_functional = [d for d in domains if d.status == "available"]

    gateway = next((d for d in domains if d.name == "gateway"), None)
    if gateway is not None and gateway.status == "unavailable":
        overall = "unavailable"
    elif degraded:
        overall = "degraded"
    else:
        overall = "healthy"

    pending = next((d for d in domains if d.name == "pending_grants"), None)
    pending_grants = int(pending.detail.get("count", 0)) if pending else 0

    return {
        "generated_at": _now_iso(),
        "overall": overall,
        "domains": [
            {
                "name": d.name,
                "status": d.status,
                "reason": d.reason,
                "detail": d.detail,
            }
            for d in domains
        ],
        "degraded": [d.name for d in degraded],
        "still_functional": [d.name for d in still_functional],
        "pending_grants": pending_grants,
    }
