"""Tests for dream insights loading and dismiss."""

import json

import pytest


@pytest.fixture
def dream_file(tmp_path, monkeypatch):
    from gateway.routes import dream as dream_routes

    path = tmp_path / "dream_insights.json"
    monkeypatch.setattr(dream_routes, "DREAM_INSIGHTS_FILE", path)
    return path


class TestDreamInsights:
    def test_load_empty_when_missing(self, dream_file):
        from gateway.routes.dream import load_dream_insights

        assert load_dream_insights() == []

    def test_load_normalizes_iso_timestamp(self, dream_file):
        from gateway.routes.dream import load_dream_insights

        dream_file.write_text(
            json.dumps(
                [
                    {
                        "insight_id": "abc",
                        "kind": "consolidation",
                        "title": "Consolidated 2 clusters",
                        "detail": "Consolidated 2 trace cluster(s)",
                        "source": "nightly_dream",
                        "confidence": 0.9,
                        "created_at": "2026-05-20T03:00:00",
                        "actions": [],
                    }
                ]
            )
        )
        rows = load_dream_insights()
        assert len(rows) == 1
        assert isinstance(rows[0]["created_at"], float)

    def test_dismiss_removes_insight(self, dream_file):
        from gateway.routes.dream import dismiss_dream_insight, load_dream_insights

        dream_file.write_text(
            json.dumps(
                [
                    {
                        "insight_id": "keep",
                        "kind": "consolidation",
                        "title": "a",
                        "detail": "a",
                        "source": "x",
                        "confidence": 1,
                        "created_at": "2026-05-20T03:00:00",
                        "actions": [],
                    },
                    {
                        "insight_id": "drop",
                        "kind": "warning",
                        "title": "b",
                        "detail": "b",
                        "source": "x",
                        "confidence": 1,
                        "created_at": "2026-05-20T03:00:00",
                        "actions": [],
                    },
                ]
            )
        )
        assert dismiss_dream_insight("drop") is True
        ids = [i["insight_id"] for i in load_dream_insights(limit=10)]
        assert ids == ["keep"]
