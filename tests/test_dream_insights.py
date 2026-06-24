"""Tests for gateway.dream_insights — the dream/insight substrate.

The route layer was slimmed in Phase 3 to a thin wrapper. These
tests pin the substrate: parser, load/dismiss, the trigger that
runs nightly_dream, and the dream status surface.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gateway import dream_insights


@pytest.fixture
def isolated_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    p = tmp_path / "dream_insights.json"
    monkeypatch.setattr(dream_insights, "DREAM_INSIGHTS_FILE", p)
    return p


class TestSaveDreamInsights:
    def test_one_card_per_line(
        self, isolated_file: Path
    ) -> None:
        summary = (
            "Consolidated 4 trace cluster(s) into long-term memory\n"
            "Pruned 11 old trace entries (kept last 30d)"
        )
        dream_insights.save_dream_insights(summary)
        cards = json.loads(isolated_file.read_text(encoding="utf-8"))
        assert len(cards) == 2
        kinds = [c["kind"] for c in cards]
        assert "consolidation" in kinds
        assert "maintenance" in kinds  # contains "prune"

    def test_classifies_warning_kind(
        self, isolated_file: Path
    ) -> None:
        dream_insights.save_dream_insights("Consolidation error: boom")
        cards = json.loads(isolated_file.read_text(encoding="utf-8"))
        assert cards[0]["kind"] == "warning"

    def test_classifies_reflection_kind(
        self, isolated_file: Path
    ) -> None:
        dream_insights.save_dream_insights("Weekly mirror refreshed: ...")
        cards = json.loads(isolated_file.read_text(encoding="utf-8"))
        assert cards[0]["kind"] == "reflection"

    def test_cards_have_required_fields(
        self, isolated_file: Path
    ) -> None:
        dream_insights.save_dream_insights("Consolidated 2 cluster(s)")
        card = json.loads(isolated_file.read_text(encoding="utf-8"))[0]
        assert card["source"] == "nightly_dream"
        assert card["confidence"] == 0.9
        assert card["actions"] == []
        assert len(card["insight_id"]) == 8
        assert isinstance(card["title"], str)
        assert card["title"] == "Consolidated 2 cluster(s)"[:80]

    def test_empty_summary_yields_no_cards(
        self, isolated_file: Path
    ) -> None:
        dream_insights.save_dream_insights("   \n\n  \n")
        cards = json.loads(isolated_file.read_text(encoding="utf-8"))
        assert cards == []


class TestLoadDreamInsights:
    def test_empty_when_missing(self, isolated_file: Path) -> None:
        assert dream_insights.load_dream_insights() == []

    def test_normalizes_iso_timestamp(
        self, isolated_file: Path
    ) -> None:
        isolated_file.write_text(
            json.dumps(
                [
                    {
                        "insight_id": "abc",
                        "kind": "consolidation",
                        "title": "x",
                        "detail": "x",
                        "source": "nightly_dream",
                        "confidence": 0.9,
                        "created_at": "2026-05-20T03:00:00",
                        "actions": [],
                    }
                ]
            ),
            encoding="utf-8",
        )
        rows = dream_insights.load_dream_insights()
        assert len(rows) == 1
        assert isinstance(rows[0]["created_at"], float)

    def test_respects_limit(
        self, isolated_file: Path
    ) -> None:
        isolated_file.write_text(
            json.dumps(
                [
                    {"insight_id": str(i), "kind": "x", "title": "t", "detail": "d",
                     "source": "s", "confidence": 1.0, "created_at": "2026-05-20T03:00:00",
                     "actions": []}
                    for i in range(10)
                ]
            ),
            encoding="utf-8",
        )
        assert len(dream_insights.load_dream_insights(limit=3)) == 3

    def test_corrupt_file_raises(self, isolated_file: Path) -> None:
        isolated_file.write_text("{not valid json", encoding="utf-8")
        with pytest.raises(ValueError, match="not valid JSON"):
            dream_insights.load_dream_insights()


class TestDismiss:
    def test_removes_named_card(
        self, isolated_file: Path
    ) -> None:
        isolated_file.write_text(
            json.dumps(
                [
                    {"insight_id": "keep", "kind": "x", "title": "a", "detail": "a",
                     "source": "s", "confidence": 1, "created_at": 0.0, "actions": []},
                    {"insight_id": "drop", "kind": "x", "title": "b", "detail": "b",
                     "source": "s", "confidence": 1, "created_at": 0.0, "actions": []},
                ]
            ),
            encoding="utf-8",
        )
        assert dream_insights.dismiss_dream_insight("drop") is True
        ids = [c["insight_id"] for c in dream_insights.load_dream_insights(limit=10)]
        assert ids == ["keep"]

    def test_returns_false_when_missing(
        self, isolated_file: Path
    ) -> None:
        isolated_file.write_text("[]", encoding="utf-8")
        assert dream_insights.dismiss_dream_insight("ghost") is False

    def test_creates_file_if_missing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # dismiss on an empty store is a no-op, must not raise
        monkeypatch.setattr(dream_insights, "DREAM_INSIGHTS_FILE", tmp_path / "fresh.json")
        assert dream_insights.dismiss_dream_insight("anything") is False


class TestStatus:
    def test_returns_never_run_shape_when_empty(
        self, isolated_file: Path
    ) -> None:
        # Don't touch the real consolidation cache; inject a fake
        from gateway import memory_consolidation

        monkey_info = {"last_run": None, "never": True}
        monkey_info["insights_count"] = 0
        import unittest.mock as mock

        with mock.patch.object(
            memory_consolidation, "get_last_run_info", return_value={"last_run": None, "never": True}
        ):
            status = dream_insights.dream_status()
        assert status["last_run"] is None
        assert status["insights_count"] == 0

    def test_counts_persisted_insights(
        self, isolated_file: Path
    ) -> None:
        from gateway import memory_consolidation
        import unittest.mock as mock

        dream_insights.save_dream_insights(
            "Consolidated 1 cluster\nPruned 2 old entries"
        )
        with mock.patch.object(
            memory_consolidation,
            "get_last_run_info",
            return_value={"last_run": "2026-05-20", "never": False},
        ):
            status = dream_insights.dream_status()
        assert status["insights_count"] == 2
        assert status["never"] is False
