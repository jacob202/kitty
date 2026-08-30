"""Tests for gateway.compute_governor — dispatch decision and cost estimation."""

from __future__ import annotations

from pathlib import Path

import pytest

from gateway import compute_governor as cg


class TestEstimateCostCad:
    def test_free_route_costs_zero(self):
        cost = cg.estimate_pass_cost_cad(cg.ROUTE_FREE)
        assert cost == 0.0

    def test_cheap_route_costs_something(self):
        cost = cg.estimate_pass_cost_cad(cg.ROUTE_CHEAP)
        assert cost > 0.0

    def test_frontier_route_costs_more_than_cheap(self):
        cheap = cg.estimate_pass_cost_cad(cg.ROUTE_CHEAP)
        frontier = cg.estimate_pass_cost_cad(cg.ROUTE_FRONTIER)
        assert frontier > cheap

    def test_unknown_route_raises(self):
        with pytest.raises(cg.GovernorError, match="unknown route"):
            cg.estimate_pass_cost_cad("nonexistent")


class TestValidateDispatch:
    def test_valid_dispatch(self):
        d = cg.Dispatch(
            task_type="implement",
            work_kind="implementation",
            subject_ref="TEST-001",
            head_sha="a" * 40,
            artifact="gateway/test.py",
            acceptance_tests=("it works",),
            allowed_scope=("gateway/",),
            exclusions=(),
            risk_class="routine",
            stopping_condition="tests pass",
        )
        errors = cg.validate_dispatch(d)
        assert errors == []

    def test_invalid_task_type(self):
        d = cg.Dispatch(
            task_type="invalid",
            work_kind="implementation",
            subject_ref="TEST-001",
            head_sha="a" * 40,
            artifact="gateway/test.py",
            acceptance_tests=("it works",),
            allowed_scope=("gateway/",),
            exclusions=(),
            risk_class="routine",
            stopping_condition="tests pass",
        )
        errors = cg.validate_dispatch(d)
        assert any("task_type" in e for e in errors)


class TestReserveState:
    def test_remaining_cad(self):
        r = cg.ReserveState(weekly_budget_cad=10.0, estimated_spend_cad=3.0)
        assert r.remaining_cad == 7.0

    def test_remaining_ratio(self):
        r = cg.ReserveState(weekly_budget_cad=10.0, estimated_spend_cad=2.5)
        assert r.remaining_ratio == 0.75


class TestLoadReserveConfig:
    def test_default_when_no_file(self, tmp_path: Path):
        config = cg.load_reserve_config(tmp_path / "nonexistent.json")
        assert config["weekly_budget_cad"] == cg.DEFAULT_RESERVE_CONFIG["weekly_budget_cad"]

    def test_valid_config_file(self, tmp_path: Path):
        config_path = tmp_path / "config.json"
        config_path.write_text('{"weekly_budget_cad": 12.0}')
        config = cg.load_reserve_config(config_path)
        assert config["weekly_budget_cad"] == 12.0
