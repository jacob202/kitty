"""Architecture fitness contracts for the Kitty/KittyBuilder seam.

These tests guard ownership and boundary invariants rather than prescribing a
new Builder state machine. The detailed lifecycle behavior remains covered by
the Builder unit/integration suites.
"""

from __future__ import annotations

import inspect
from datetime import datetime, timezone
from pathlib import Path

from gateway import builder_initiative as bi
from gateway import builder_loop as bl
from gateway import builder_run as br
from gateway.app import app
from gateway.models.builder import (
    EvidenceCriterion,
    Mission,
    MissionEvidencePlan,
    MissionExecution,
    MissionOrigin,
    MissionState,
)


def test_production_mount_exposes_one_canonical_builder_command_boundary():
    """The shipped app must not reintroduce the retired action route."""
    paths = set(app.openapi()["paths"])

    assert "/builder/initiative" in paths
    assert "/builder/command" in paths
    assert "/builder/action" not in paths


def test_approved_mission_is_the_durable_idempotent_handoff(tmp_path: Path):
    """Mission submission materializes Builder state without duplicate tasks."""
    db_path = tmp_path / "builder_queue.db"
    mission = Mission(
        mission_id="architecture-fitness-v1",
        objective="Preserve the Kitty Builder boundary",
        approved_at=datetime(2026, 8, 9, tzinfo=timezone.utc),
        state=MissionState.approved,
        origin=MissionOrigin(base_sha="a" * 40),
        execution=MissionExecution(allowed_paths=["gateway/routes/builder.py"]),
        evidence_plan=MissionEvidencePlan(
            acceptance_criteria=[
                EvidenceCriterion(description="the handoff is durable")
            ]
        ),
    )

    first = bi.submit_mission(mission, db_path=db_path, repo_root=tmp_path)
    second = bi.submit_mission(mission, db_path=db_path, repo_root=tmp_path)

    assert first["status"] == "created"
    assert second["status"] == "unchanged"
    initiative = bi.get_initiative(mission.mission_id, db_path=db_path)
    assert initiative is not None
    assert initiative["packets"]
    assert len(bi.list_initiatives(db_path=db_path)) == 1


def test_builder_clients_use_projection_and_canonical_commands_only():
    """The cockpit remains a client of Builder, not a second state owner."""
    surface = (
        Path(__file__).parents[1]
        / "gateway"
        / "kitty-chat"
        / "src"
        / "components"
        / "BuilderSurface.tsx"
    ).read_text(encoding="utf-8")

    assert "useOperatorCommand" in surface
    assert "useBuilderAction" not in surface
    assert "/builder/action" not in surface
    assert "sqlite" not in surface.lower()


def test_builder_execution_keeps_durable_evidence_and_recovery_gates():
    """Workers/LLMs cannot replace Builder's evidence and recovery gates."""
    loop_source = inspect.getsource(bl.run_packet)
    run_source = inspect.getsource(br.run_initiative)

    required_loop_calls = (
        "ba.record_implementation_result",
        "ba.run_validation",
        "ba.record_review_result",
        "_close_provider_exhaustion",
    )
    for call in required_loop_calls:
        assert call in loop_source

    assert "provider_exhausted" in run_source
    assert "pause_initiative" in run_source
