"""Tests for gateway.builder_status — Builder status projection."""

from __future__ import annotations

from pathlib import Path

import pytest

from gateway import builder_status as bs


class TestRuntimeProjection:
    def test_projection_schema_version(self):
        assert bs.SCHEMA_VERSION >= 1

    def test_budget_projection_fields(self):
        budget = bs.BudgetProjection(used=0, max_attempts=3, exhausted=False)
        d = budget.__dict__
        assert d["used"] == 0
        assert d["max_attempts"] == 3
        assert d["exhausted"] is False

    def test_lease_projection_none(self):
        result = bs._lease_projection(None)
        assert result is None

    def test_failure_kind_cancelled(self):
        result = bs._failure_kind(
            task_state="cancelled",
            exhausted=False,
            attempt=None,
            run=None,
            run_infrastructure_failure=False,
            last_event=None,
        )
        assert result == "cancelled"

    def test_failure_kind_exhausted(self):
        result = bs._failure_kind(
            task_state="failed",
            exhausted=True,
            attempt=None,
            run=None,
            run_infrastructure_failure=False,
            last_event=None,
        )
        assert result == "exhausted"

    def test_failure_kind_none_when_running(self):
        result = bs._failure_kind(
            task_state="running",
            exhausted=False,
            attempt=None,
            run=None,
            run_infrastructure_failure=False,
            last_event=None,
        )
        assert result is None


class TestMaxAttempts:
    def test_valid_policy(self):
        issues: list[str] = []
        result = bs._max_attempts({"max_attempts": 5}, issues)
        assert result == 5
        assert issues == []

    def test_default_when_missing(self):
        issues: list[str] = []
        result = bs._max_attempts({}, issues)
        assert result is not None  # default from ba

    def test_none_when_policy_missing(self):
        issues: list[str] = []
        result = bs._max_attempts(None, issues)
        assert result is None
        assert len(issues) > 0
