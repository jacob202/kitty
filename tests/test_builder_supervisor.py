"""Tests for the Builder supervisor preflight_packet function."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from gateway import builder_initiative as bi
from gateway import builder_queue as bq
from gateway import builder_supervisor as bs


def _apply_test_manifest(db_path: Path) -> dict[str, Any]:
    """Apply a minimal valid manifest to the test DB and return the result."""
    manifest: dict[str, Any] = {
        "manifest_version": 1,
        "initiative_id": "TEST-PREFLIGHT-001",
        "title": "Test preflight initiative",
        "description": "A test initiative for preflight validation",
        "packets": [
            {
                "id": "PF-001",
                "title": "Test packet",
                "objective": "Test that preflight works",
                "acceptance_criteria": ["preflight returns a structured result"],
                "allowed_paths": ["tests/"],
                "validation_commands": ["echo ok"],
                "policy": {"max_attempts": 2, "priority": 10},
            },
        ],
    }
    return bi.apply_manifest(manifest, db_path=db_path, base_sha="a" * 40)


@pytest.fixture()
def populated_db(tmp_db: Path) -> Path:
    """DB with one initiative and one packet applied."""
    _apply_test_manifest(tmp_db)
    return tmp_db


class TestPreflightPacket:
    """Read-only preflight review of a single packet."""

    def test_returns_run_for_eligible_packet(self, populated_db: Path) -> None:
        result = bs.preflight_packet(
            "TEST-PREFLIGHT-001", "PF-001", db_path=populated_db,
        )
        assert result["action"] == "run"
        assert result["route"] == "free"
        assert result["estimated_cost_cad"] == 0.0
        assert result["packet"]["initiative_id"] == "TEST-PREFLIGHT-001"
        assert result["packet"]["packet_id"] == "PF-001"
        assert isinstance(result["budget"], dict)
        assert "weekly_budget_cad" in result["budget"]
        assert isinstance(result["eligibility"], dict)
        assert result["eligibility"]["state"] == "eligible"
        assert result["data_quality"]["state"] == "complete"

    def test_refuses_unknown_initiative(self, populated_db: Path) -> None:
        result = bs.preflight_packet(
            "DOES-NOT-EXIST", "PF-001", db_path=populated_db,
        )
        assert result["action"] == "refuse"
        assert any("not found" in r for r in result["reasons"])
        assert result["route"] is None

    def test_refuses_unknown_packet(self, populated_db: Path) -> None:
        result = bs.preflight_packet(
            "TEST-PREFLIGHT-001", "DOES-NOT-EXIST", db_path=populated_db,
        )
        assert result["action"] == "refuse"
        assert any("not found" in r for r in result["reasons"])
        assert result["route"] is None

    def test_blocks_paused_initiative_packet(self, populated_db: Path) -> None:
        bi.pause_initiative(
            "TEST-PREFLIGHT-001", reason="test pause", db_path=populated_db,
        )
        result = bs.preflight_packet(
            "TEST-PREFLIGHT-001", "PF-001", db_path=populated_db,
        )
        # Paused initiative makes the packet not eligible.
        assert result["action"] in ("blocked", "refuse")
        assert result["eligibility"]["state"] != "eligible"

    def test_does_not_create_attempt(self, populated_db: Path) -> None:
        """Preflight must be read-only: no attempt row is created."""
        from gateway import builder_attempt as ba

        before = ba.list_attempts(
            "TEST-PREFLIGHT-001", "PF-001", db_path=populated_db,
        )
        bs.preflight_packet(
            "TEST-PREFLIGHT-001", "PF-001", db_path=populated_db,
        )
        after = ba.list_attempts(
            "TEST-PREFLIGHT-001", "PF-001", db_path=populated_db,
        )
        assert len(before) == len(after) == 0

    def test_does_not_change_task_state(self, populated_db: Path) -> None:
        """Preflight must not change the task state."""
        task = bq.get_task(
            str(
                bi.get_initiative("TEST-PREFLIGHT-001", db_path=populated_db)
                ["packets"][0]["task_id"]
            ),
            db_path=populated_db,
        )
        state_before = task["state"]
        bs.preflight_packet(
            "TEST-PREFLIGHT-001", "PF-001", db_path=populated_db,
        )
        task_after = bq.get_task(str(task["id"]), db_path=populated_db)
        assert task_after["state"] == state_before

    def test_cost_basis_labelled_as_estimate(self, populated_db: Path) -> None:
        result = bs.preflight_packet(
            "TEST-PREFLIGHT-001", "PF-001", db_path=populated_db,
        )
        assert "NOT a provider meter" in result["cost_basis"]

    def test_dispatch_hash_is_stable(self, populated_db: Path) -> None:
        r1 = bs.preflight_packet(
            "TEST-PREFLIGHT-001", "PF-001", db_path=populated_db,
        )
        r2 = bs.preflight_packet(
            "TEST-PREFLIGHT-001", "PF-001", db_path=populated_db,
        )
        assert r1["dispatch_hash"] == r2["dispatch_hash"]

    def test_budget_includes_weekly_remaining(self, populated_db: Path) -> None:
        result = bs.preflight_packet(
            "TEST-PREFLIGHT-001", "PF-001", db_path=populated_db,
        )
        budget = result["budget"]
        assert budget["weekly_budget_cad"] >= 0
        assert budget["remaining_cad"] >= 0
        assert budget["remaining_cad"] <= budget["weekly_budget_cad"]
        assert isinstance(budget["basis"], str)
        assert "estimate" in budget["basis"].lower()
