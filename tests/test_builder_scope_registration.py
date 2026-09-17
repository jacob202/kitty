"""Regression pins for the 2026-09-17 Builder launch-outage failure classes.

The outage surfaced three deterministic launch blockers that were each only
discovered after a live packet had already claimed work:

1. a stale canonical checkout whose CLI contract no longer matched the caller
   (fixed by restoring canonical main; no test can pin a working tree);
2. a model route naming a model absent from the provider catalog, which was
   collapsed into "all configured paid worker providers were unavailable";
3. a packet scope naming paths with no registered KX resource, which consumed
   a claim and -- repeated three times -- escalated the packet into
   ``recovery_budget_exhausted``.

These tests pin the parts that are deterministic and locally knowable, so the
gap is caught at CI time rather than after paid work and retry budget are spent.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gateway import agent_coordination as ac

ROOT = Path(__file__).resolve().parents[1]

# The exact scopes from the failing R-7 packet
# (docs/initiatives/kitty-release-r7-v2.json -> kitty-release-r7-degraded).
R7_DEGRADED_SCOPES = (
    "gateway/health_surface.py",
    "tests/test_health_surface.py",
    "tests/test_health_surface_degraded.py",
)


@pytest.mark.parametrize("scope", R7_DEGRADED_SCOPES)
def test_r7_degraded_packet_scopes_resolve_to_a_resource(scope: str) -> None:
    """Every scope the R-7 degraded packet declares must resolve.

    This is the incident regression: an unregistered scope raises
    ``RunnerError: Builder scope '...' resolves to no registered KX resource``
    after the task has been claimed.
    """
    assert ac.resolve_paths_to_resources([scope]), (
        f"Builder scope {scope!r} resolves to no registered KX resource; "
        "register it in coordination/resources.yaml before dispatch"
    )


def test_r7_degraded_manifest_scopes_match_this_regression() -> None:
    """Keep this file honest: the pin must track the real packet manifest."""
    manifest = json.loads(
        (ROOT / "docs" / "initiatives" / "kitty-release-r7-v2.json").read_text(
            encoding="utf-8"
        )
    )
    packet = next(
        p for p in manifest["packets"] if p["id"] == "kitty-release-r7-degraded"
    )
    assert tuple(packet["allowed_paths"]) == R7_DEGRADED_SCOPES
