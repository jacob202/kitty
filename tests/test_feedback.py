"""Tests for gateway.feedback — feedback and error log substrate.

The route layer was slimmed in Phase 3 to a thin wrapper. These
tests pin the substrate: input validation, write semantics, and
the empty-state contract.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gateway import feedback


@pytest.fixture
def isolated_logs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    fb = tmp_path / "feedback.jsonl"
    err = tmp_path / "kitty_errors.jsonl"
    monkeypatch.setattr(feedback, "FEEDBACK_LOG", fb)
    monkeypatch.setattr(feedback, "ERROR_LOG", err)
    return fb, err


class TestLogFeedback:
    def test_appends_one_line(self, isolated_logs: tuple[Path, Path]) -> None:
        fb_path, _ = isolated_logs
        feedback.log_feedback({"type": "thumbs-up"})
        assert fb_path.exists()
        lines = fb_path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record["type"] == "thumbs-up"
        assert isinstance(record["timestamp"], (int, float))

    def test_rejects_non_dict(self, isolated_logs: tuple[Path, Path]) -> None:
        with pytest.raises(TypeError, match="feedback payload must be a dict"):
            feedback.log_feedback("not a dict")  # type: ignore[arg-type]

    def test_preserves_extra_fields(self, isolated_logs: tuple[Path, Path]) -> None:
        fb_path, _ = isolated_logs
        feedback.log_feedback({"type": "rating", "score": 5, "comment": "great"})
        record = json.loads(fb_path.read_text(encoding="utf-8").strip())
        assert record["score"] == 5
        assert record["comment"] == "great"

    def test_raises_on_write_failure(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The old route swallowed the I/O error. The new module raises."""
        # Place a regular file where a directory is needed — mkdir fails.
        blocker = tmp_path / "blocker"
        blocker.write_text("not a directory", encoding="utf-8")
        broken = blocker / "nested" / "log.jsonl"
        monkeypatch.setattr(feedback, "FEEDBACK_LOG", broken)
        with pytest.raises(OSError):
            feedback.log_feedback({"type": "x"})


class TestLogError:
    def test_appends_one_line(self, isolated_logs: tuple[Path, Path]) -> None:
        _, err_path = isolated_logs
        feedback.log_error({"error_type": "network", "detail": "dns"})
        record = json.loads(err_path.read_text(encoding="utf-8").strip())
        assert record["error_type"] == "network"
        assert record["detail"] == "dns"
        assert "timestamp" in record

    def test_rejects_non_dict(self, isolated_logs: tuple[Path, Path]) -> None:
        with pytest.raises(TypeError, match="error payload must be a dict"):
            feedback.log_error(42)  # type: ignore[arg-type]

    def test_raises_on_write_failure(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        blocker = tmp_path / "blocker"
        blocker.write_text("not a directory", encoding="utf-8")
        broken = blocker / "nested" / "err.jsonl"
        monkeypatch.setattr(feedback, "ERROR_LOG", broken)
        with pytest.raises(OSError):
            feedback.log_error({"error_type": "x"})


class TestStats:
    def test_empty_when_no_logs(self, isolated_logs: tuple[Path, Path]) -> None:
        stats = feedback.get_feedback_stats()
        assert stats["total_feedback"] == 0
        assert stats["total_errors"] == 0
        assert stats["feedback_by_type"] == {}
        assert stats["errors_by_type"] == {}
        assert stats["recent_feedback"] == []
        assert stats["recent_errors"] == []

    def test_counts_and_buckets(self, isolated_logs: tuple[Path, Path]) -> None:
        fb_path, err_path = isolated_logs
        feedback.log_feedback({"type": "thumbs-up"})
        feedback.log_feedback({"type": "thumbs-up"})
        feedback.log_feedback({"type": "thumbs-down"})
        feedback.log_error({"error_type": "network"})
        feedback.log_error({"error_type": "timeout"})
        feedback.log_error({"error_type": "network"})

        stats = feedback.get_feedback_stats()
        assert stats["total_feedback"] == 3
        assert stats["total_errors"] == 3
        assert stats["feedback_by_type"]["thumbs-up"] == 2
        assert stats["feedback_by_type"]["thumbs-down"] == 1
        assert stats["errors_by_type"]["network"] == 2
        assert stats["errors_by_type"]["timeout"] == 1

    def test_recent_window_is_ten(self, isolated_logs: tuple[Path, Path]) -> None:
        fb_path, _ = isolated_logs
        for i in range(15):
            feedback.log_feedback({"type": "x", "n": i})
        stats = feedback.get_feedback_stats()
        assert len(stats["recent_feedback"]) == 10
        # Window keeps the most recent ten — n=5..14
        ns = [entry["n"] for entry in stats["recent_feedback"]]
        assert ns == list(range(5, 15))

    def test_skips_malformed_lines(
        self, isolated_logs: tuple[Path, Path]
    ) -> None:
        fb_path, _ = isolated_logs
        fb_path.write_text(
            'not-json\n'
            + json.dumps({"type": "valid"}) + "\n"
            + '{"type": "broken"\n',
            encoding="utf-8",
        )
        stats = feedback.get_feedback_stats()
        assert stats["total_feedback"] == 1
        assert stats["feedback_by_type"] == {"valid": 1}
