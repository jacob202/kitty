"""Tests for gateway.builder_supervisor API surface — supervisor status and tick."""

from __future__ import annotations

from pathlib import Path

import pytest

from gateway import builder_supervisor as bs


class TestDispatchableCounts:
    def test_returns_dict_with_expected_keys(self):
        counts = bs.dispatchable_counts()
        assert "now" in counts
        assert "on_hold" in counts
        assert isinstance(counts["now"], int)
        assert isinstance(counts["on_hold"], int)


class TestActiveInitiatives:
    def test_returns_list(self):
        result = bs.active_initiatives()
        assert isinstance(result, list)


class TestBudgetSummary:
    def test_returns_budget_dict(self):
        summary = bs.budget_summary()
        assert "weekly_budget_cad" in summary
        assert "estimated_spend_cad" in summary
        assert "remaining_cad" in summary
        assert "runs" in summary
        assert "basis" in summary
        assert isinstance(summary["weekly_budget_cad"], float)
        assert isinstance(summary["remaining_cad"], float)


class TestControlPlaneSummary:
    def test_returns_expected_keys(self):
        summary = bs.control_plane_summary()
        assert "active_runs" in summary
        assert "eligible_now" in summary
        assert "on_hold" in summary
        assert "lock_path" in summary
        assert "budget" in summary
