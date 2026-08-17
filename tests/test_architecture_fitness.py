"""Architecture fitness contracts for the Kitty/KittyBuilder seam.

These tests guard ownership and boundary invariants rather than prescribing a
new Builder state machine. The detailed lifecycle behavior remains covered by
the Builder unit/integration suites.
"""

from __future__ import annotations

import inspect
from pathlib import Path

from gateway import builder_initiative as bi
from gateway import builder_loop as bl
from gateway import builder_run as br
from gateway.app import app


def test_production_mount_exposes_one_canonical_builder_command_boundary():
    """The shipped app must not reintroduce the retired action route."""
    paths = set(app.openapi()["paths"])

    assert "/builder/initiative" not in paths
    assert "/builder/command" in paths
    assert "/builder/action" not in paths


def test_legacy_builder_action_adapter_is_retired():
    """The retired route must not survive as an unmounted compatibility path."""
    repo_root = Path(__file__).parents[1]
    assert not (repo_root / "gateway" / "routes" / "builder_control.py").exists()

    action_queue_source = (repo_root / "gateway" / "action_queue.py").read_text(
        encoding="utf-8"
    )
    tiers_source = (repo_root / "config" / "action_tiers.json").read_text(
        encoding="utf-8"
    )
    for kind in (
        "builder.run_next",
        "builder.pause_initiative",
        "builder.resume_initiative",
        "builder.cancel_task",
        "builder.cleanup",
    ):
        assert kind not in action_queue_source
        assert kind not in tiers_source


def test_canonical_manifest_is_the_durable_idempotent_handoff(tmp_path: Path):
    """The executable manifest materializes its real packet graph exactly once."""
    db_path = tmp_path / "builder_queue.db"
    manifest = {
        "manifest_version": 1,
        "initiative_id": "architecture-fitness-v1",
        "title": "Preserve the Kitty Builder boundary",
        "packets": [
            {
                "id": "P1",
                "title": "First bounded packet",
                "objective": "Create the first bounded change",
                "depends_on": [],
                "acceptance_criteria": ["first packet is durable"],
                "allowed_paths": ["gateway/routes/builder.py"],
                "validation_commands": ["pytest -q tests/test_builder_routes.py"],
            },
            {
                "id": "P2",
                "title": "Dependent packet",
                "objective": "Prove dependency preservation",
                "depends_on": ["P1"],
                "acceptance_criteria": ["dependency graph is durable"],
                "allowed_paths": ["gateway/builder_initiative.py"],
                "validation_commands": ["pytest -q tests/test_builder_initiative.py"],
            },
        ],
    }

    first = bi.apply_manifest(manifest, db_path=db_path, base_sha="a" * 40)
    second = bi.apply_manifest(manifest, db_path=db_path, base_sha="a" * 40)

    assert first["status"] == "created"
    assert second["status"] == "unchanged"
    initiative = bi.get_initiative(manifest["initiative_id"], db_path=db_path)
    assert initiative is not None
    assert [p["packet_id"] for p in initiative["packets"]] == ["P1", "P2"]
    assert initiative["packets"][1]["depends_on"] == ["P1"]


def test_no_second_public_mission_model_survives():
    """Builder exposes the executable manifest contract, not a parallel dialect."""
    from gateway.models import builder as builder_models

    assert not hasattr(builder_models, "Mission")
    assert not hasattr(bi, "mission_to_manifest")
    assert not hasattr(bi, "submit_mission")


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
