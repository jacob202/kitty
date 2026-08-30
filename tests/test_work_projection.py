"""Tests for gateway.work_projection — Work item projection."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from gateway.work_projection import _build, project_work_snapshot


class TestBuild:
    def test_returns_schema_version(self):
        result = _build({})
        assert result["schema_version"] == 1

    def test_empty_initiatives(self):
        result = _build({"initiatives": []})
        assert result["items"] == []
        assert result["total_items"] == 0

    def test_observed_at_is_utc(self):
        result = _build({})
        assert result["observed_at"].endswith("Z")

    def test_valid_until_after_observed(self):
        result = _build({})
        assert result["valid_until"] > result["observed_at"]


class TestProjectWorkSnapshot:
    def test_callable(self):
        result = project_work_snapshot({})
        assert "schema_version" in result
        assert "items" in result
