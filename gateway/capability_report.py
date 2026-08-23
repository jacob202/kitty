"""Startup capability report (QoL Packet 07).

Surfaces, at Kitty startup, a concise summary of what is available, degraded,
or unavailable — without equating a missing optional dependency (e.g. Ollama)
with Kitty being broken. The report is derived from real probes plus the
live automation supervisor state and rendered as one ASCII block.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Mapping

import httpx

from gateway.automation_supervisor import supervisor
from gateway.image_backends import get_registry
from gateway.memory import _probe_memory_backend

AVAILABLE = "available"
DEGRADED = "degraded"
UNAVAILABLE = "unavailable"
OPTIONAL_UNAVAILABLE = "optional-unavailable"
UNKNOWN = "unknown"

VALID_STATUSES = frozenset(
    {AVAILABLE, DEGRADED, UNAVAILABLE, OPTIONAL_UNAVAILABLE, UNKNOWN}
)

OLLAMA_BASE = "http://localhost:11434"
OLLAMA_TIMEOUT_SECONDS = 3.0

# Feature -> capabilities the feature requires to be functional.
_FEATURE_REQUIRES: dict[str, tuple[str, ...]] = {
    "Explicit memory": ("Database",),
    "Pinned context": ("Database",),
    "Image generation": ("Image Lab",),
    "Scheduled automation": ("Automation",),
}

_CAPABILITY_ORDER = (
    "Gateway",
    "Database",
    "Memory",
    "Automation",
    "Image Lab",
    "Image Queue",
    "Telegram",
)


@dataclass(frozen=True)
class Capability:
    """Diagnostic status of a single capability."""

    name: str
    status: str
    detail: str | None = None
    optional: bool = False


@dataclass
class CapabilityReport:
    """Ordered capability snapshot plus derived summaries."""

    capabilities: list[Capability]
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def get(self, name: str) -> Capability | None:
        return next((c for c in self.capabilities if c.name == name), None)

    @property
    def available(self) -> list[Capability]:
        return [c for c in self.capabilities if c.status == AVAILABLE]

    @property
    def degraded_items(self) -> list[Capability]:
        return [c for c in self.capabilities if c.status != AVAILABLE]

    @property
    def still_functional(self) -> list[str]:
        available_names = {c.name for c in self.available}
        return [
            feature
            for feature, requires in _FEATURE_REQUIRES.items()
            if requires and all(req in available_names for req in requires)
        ]

    @property
    def overall(self) -> str:
        if all(
            c.status == AVAILABLE for c in self.capabilities if not c.optional
        ):
            return AVAILABLE
        return DEGRADED


def build_capability_report(probes: Mapping[str, Capability]) -> CapabilityReport:
    """Assemble a report, ordering known capabilities first, extras after."""
    ordered = [probes[name] for name in _CAPABILITY_ORDER if name in probes]
    extras = [
        probes[name] for name in probes if name not in _CAPABILITY_ORDER
    ]
    return CapabilityReport(capabilities=ordered + extras)


def render_capability_report(report: CapabilityReport) -> str:
    """Render the report as the 'KITTY READY' ASCII block."""
    lines = ["KITTY READY"]
    available = report.available
    if available:
        lines.append(" / ".join(f"{c.name} ✓" for c in available))
    degraded = report.degraded_items
    if degraded:
        width = max(len(c.name) for c in degraded) + 2
        lines.append("Degraded")
        for c in degraded:
            lines.append(f"{c.name:<{width}}{c.status}")
    functional = report.still_functional
    if functional:
        lines.append("Still functional")
        lines.append(" / ".join(functional))
    return "\n".join(lines)


async def probe_capabilities() -> CapabilityReport:
    """Probe real subsystems and produce a live capability report."""
    probes: list[Capability] = [
        Capability(name="Gateway", status=AVAILABLE)
    ]

    database_ok = await _probe_database()
    if database_ok:
        probes.append(Capability(name="Database", status=AVAILABLE))
        try:
            _probe_memory_backend()
            probes.append(Capability(name="Memory", status=AVAILABLE))
        except Exception as exc:  # noqa: BLE001 - classification boundary
            probes.append(
                Capability(
                    name="Memory",
                    status=DEGRADED,
                    detail=(
                        "memory backend initialisation failed "
                        f"({type(exc).__name__}); explicit/pinned memory store "
                        "remains reachable"
                    ),
                )
            )
    else:
        probes.append(
            Capability(name="Database", status=UNAVAILABLE, detail="database probe failed")
        )
        probes.append(
            Capability(name="Memory", status=UNAVAILABLE, detail="database unreachable")
        )

    probes.append(
        Capability(
            name="Automation",
            status=_capability_from_supervisor(_supervisor_status("cron"), database_ok),
        )
    )
    probes.append(Capability(name="Image Lab", status=await _probe_image_lab()))
    probes.append(
        Capability(
            name="Image Queue",
            status=_capability_from_supervisor(_supervisor_status("image-batch-worker"), True),
        )
    )
    probes.append(Capability(name="Telegram", status=_probe_telegram()))
    probes.append(
        Capability(
            name="Ollama",
            status=await _probe_ollama(),
            optional=True,
        )
    )
    return CapabilityReport(capabilities=probes)


async def _probe_database() -> bool:
    from gateway.db import connect
    from gateway.paths import KITTY_DB_FILE

    try:
        conn = connect(db_file=KITTY_DB_FILE)
        try:
            conn.execute("SELECT 1")
            return True
        finally:
            conn.close()
    except Exception:  # noqa: BLE001 - probe boundary
        return False


def _probe_telegram() -> str:
    from gateway.telegram_bot import is_configured

    if not is_configured():
        return UNAVAILABLE
    return _capability_from_supervisor(_supervisor_status("telegram"), True)


async def _probe_image_lab() -> str:
    try:
        for backend in get_registry().get_all():
            if await backend.is_available():
                return AVAILABLE
        return UNAVAILABLE
    except Exception:  # noqa: BLE001 - probe boundary
        return UNKNOWN


def _capability_from_supervisor(status: dict[str, str], dependency_ok: bool) -> str:
    if not dependency_ok:
        return UNAVAILABLE
    current = status.get("status") or UNKNOWN
    if current in {"available", "stale"}:
        return AVAILABLE if current == "available" else DEGRADED
    if current == "degraded":
        return DEGRADED
    if current in {"unavailable"}:
        return UNAVAILABLE
    return UNKNOWN


async def _probe_ollama() -> str:
    try:
        async with httpx.AsyncClient(timeout=OLLAMA_TIMEOUT_SECONDS) as client:
            response = await client.get(f"{OLLAMA_BASE}/api/tags")
        if response.status_code < 400:
            return AVAILABLE
        return UNAVAILABLE
    except (httpx.ConnectError, httpx.TimeoutException, OSError):
        return OPTIONAL_UNAVAILABLE
    except Exception:  # noqa: BLE001 - probe boundary
        return UNKNOWN


def _supervisor_status(name: str) -> dict[str, str]:
    return supervisor.get_status(name)
