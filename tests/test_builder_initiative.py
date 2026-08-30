"""Tests for gateway.builder_initiative — manifest validation and packet eligibility."""

from __future__ import annotations

from pathlib import Path

import pytest

from gateway import builder_initiative as bi


class TestValidateManifest:
    def test_valid_manifest_returns_empty_errors(self):
        manifest = {
            "manifest_version": 1,
            "initiative_id": "TEST-VAL-001",
            "title": "Test initiative",
            "packets": [
                {
                    "id": "PK-001",
                    "title": "Test packet",
                    "objective": "A test objective",
                    "acceptance_criteria": ["it works"],
                    "allowed_paths": ["tests/"],
                },
            ],
        }
        errors = bi.validate_manifest(manifest)
        assert errors == []

    def test_missing_title_returns_error(self):
        manifest = {
            "manifest_version": 1,
            "initiative_id": "TEST-VAL-002",
            "packets": [
                {
                    "id": "PK-001",
                    "title": "Test packet",
                    "objective": "Test",
                    "acceptance_criteria": ["it works"],
                    "allowed_paths": ["tests/"],
                },
            ],
        }
        errors = bi.validate_manifest(manifest)
        assert any("title" in e for e in errors)

    def test_invalid_initiative_id_returns_error(self):
        manifest = {
            "manifest_version": 1,
            "initiative_id": "!!!INVALID!!!",
            "title": "Test",
            "packets": [
                {
                    "id": "PK-001",
                    "title": "Test",
                    "objective": "Test",
                    "acceptance_criteria": ["it works"],
                    "allowed_paths": ["tests/"],
                },
            ],
        }
        errors = bi.validate_manifest(manifest)
        assert any("initiative_id" in e for e in errors)


class TestDeriveInitiativeState:
    def test_active_when_eligible(self):
        state = bi.derive_initiative_state(
            stored_state="active",
            total_packets=1,
            done_count=0,
            has_blocked=False,
            has_failed=False,
            has_exhausted=False,
            has_eligible=True,
        )
        assert state == "active"

    def test_completed_when_all_done(self):
        state = bi.derive_initiative_state(
            stored_state="active",
            total_packets=2,
            done_count=2,
            has_blocked=False,
            has_failed=False,
            has_exhausted=False,
            has_eligible=False,
        )
        assert state == "completed"

    def test_paused_when_nothing_eligible(self):
        state = bi.derive_initiative_state(
            stored_state="active",
            total_packets=2,
            done_count=0,
            has_blocked=False,
            has_failed=False,
            has_exhausted=False,
            has_eligible=False,
        )
        assert state == "paused"


class TestDerivePacketEligibility:
    def test_eligible_when_queued_and_deps_done(self):
        result = bi.derive_packet_eligibility(
            packet_id="PK-001",
            task_state="queued",
            depends_on=[],
            task_states={},
            exhausted_packet_ids=set(),
        )
        assert result["state"] == "eligible"

    def test_not_queued_when_task_not_queued(self):
        result = bi.derive_packet_eligibility(
            packet_id="PK-001",
            task_state="running",
            depends_on=[],
            task_states={},
            exhausted_packet_ids=set(),
        )
        assert result["state"] == "not_queued"

    def test_blocked_when_dependency_failed(self):
        result = bi.derive_packet_eligibility(
            packet_id="PK-002",
            task_state="queued",
            depends_on=["PK-001"],
            task_states={"PK-001": "failed"},
            exhausted_packet_ids=set(),
        )
        assert result["state"] == "blocked"
        assert "PK-001" in result["blocked_by"]

    def test_waiting_when_dependency_not_done(self):
        result = bi.derive_packet_eligibility(
            packet_id="PK-002",
            task_state="queued",
            depends_on=["PK-001"],
            task_states={"PK-001": "running"},
            exhausted_packet_ids=set(),
        )
        assert result["state"] == "waiting"
        assert "PK-001" in result["blocked_by"]
