"""Tests for gateway.perf — performance stat substrate.

The route layer was slimmed in Phase 3 to a thin wrapper. These
tests pin the substrate: input validation, the windowed aggregations,
the recent window, and the empty-state contract.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gateway import cron, perf


@pytest.fixture
def isolated_log(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    log = tmp_path / "perf_stats.jsonl"
    monkeypatch.setattr(perf, "PERF_LOG", log)
    return log


@pytest.fixture(autouse=True)
def _clear_cron_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin the cron store to a tmp file so the perf stats don't read
    whatever happens to be on disk in the developer's repo."""
    cron_db = tmp_path / "cron_schedules.db"
    monkeypatch.setattr(cron, "CRON_DB", cron_db)


class TestLogPerfStat:
    def test_appends_one_line(self, isolated_log: Path) -> None:
        perf.log_perf_stat({"latency_ms": 123, "tokens": 10})
        record = json.loads(isolated_log.read_text(encoding="utf-8").strip())
        assert record["latency_ms"] == 123
        assert record["tokens"] == 10
        assert isinstance(record["timestamp"], (int, float))

    def test_rejects_non_dict(self, isolated_log: Path) -> None:
        with pytest.raises(TypeError, match="perf stat must be a dict"):
            perf.log_perf_stat([1, 2, 3])  # type: ignore[arg-type]

    def test_raises_on_write_failure(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        blocker = tmp_path / "blocker"
        blocker.write_text("not a directory", encoding="utf-8")
        broken = blocker / "nested" / "log.jsonl"
        monkeypatch.setattr(perf, "PERF_LOG", broken)
        with pytest.raises(OSError):
            perf.log_perf_stat({"latency_ms": 1})


class TestGetPerfStats:
    def test_empty_when_no_data(self, isolated_log: Path) -> None:
        stats = perf.get_perf_stats(window_hours=24)
        assert stats["total_requests"] == 0
        assert stats["avg_latency_ms"] == 0
        assert stats["max_latency_ms"] == 0
        assert stats["min_latency_ms"] == 0
        assert stats["total_tokens"] == 0
        assert stats["avg_tokens"] == 0
        assert stats["window_hours"] == 24
        assert stats["schedules"] == []

    def test_window_filters_old_entries(
        self, isolated_log: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        old_ts = 1_000_000.0  # long ago
        new_ts = perf.time.time()
        rows = [
            {"latency_ms": 100, "tokens": 5, "timestamp": old_ts},
            {"latency_ms": 200, "tokens": 6, "timestamp": new_ts},
        ]
        isolated_log.write_text(
            "\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8"
        )
        stats = perf.get_perf_stats(window_hours=24)
        assert stats["total_requests"] == 1
        assert stats["avg_latency_ms"] == 200
        assert stats["total_tokens"] == 6

    def test_aggregates_latency_and_tokens(self, isolated_log: Path) -> None:
        now = perf.time.time()
        rows = [
            {"latency_ms": 100, "tokens": 10, "timestamp": now},
            {"latency_ms": 200, "tokens": 20, "timestamp": now},
            {"latency_ms": 300, "tokens": 30, "timestamp": now},
        ]
        isolated_log.write_text(
            "\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8"
        )
        stats = perf.get_perf_stats(window_hours=24)
        assert stats["total_requests"] == 3
        assert stats["avg_latency_ms"] == 200
        assert stats["max_latency_ms"] == 300
        assert stats["min_latency_ms"] == 100
        assert stats["total_tokens"] == 60
        assert stats["avg_tokens"] == 20

    def test_rejects_non_positive_window(
        self, isolated_log: Path
    ) -> None:
        with pytest.raises(ValueError, match="window_hours"):
            perf.get_perf_stats(window_hours=0)
        with pytest.raises(ValueError, match="window_hours"):
            perf.get_perf_stats(window_hours=-1)  # type: ignore[arg-type]

    def test_reports_active_schedule_count(
        self, isolated_log: Path
    ) -> None:
        cron.schedule("a", "brief.refresh", "daily", "07:00")
        cron.schedule("b", "nudges.check", "interval", "30")
        cron.toggle(cron.list_schedules()[0]["id"])  # disable the first
        stats = perf.get_perf_stats(window_hours=24)
        assert stats["active_schedules"] == 1
        assert len(stats["schedules"]) == 2


class TestGetRecentStats:
    def test_empty_when_no_data(self, isolated_log: Path) -> None:
        result = perf.get_recent_stats(limit=10)
        assert result == {"stats": [], "count": 0}

    def test_returns_newest_first(
        self, isolated_log: Path
    ) -> None:
        now = perf.time.time()
        for i in range(5):
            perf.log_perf_stat({"n": i, "timestamp": now})
        result = perf.get_recent_stats(limit=3)
        ns = [r["n"] for r in result["stats"]]
        assert ns == [4, 3, 2]
        assert result["count"] == 3

    def test_rejects_non_positive_limit(self, isolated_log: Path) -> None:
        with pytest.raises(ValueError, match="limit"):
            perf.get_recent_stats(limit=0)

    def test_skips_malformed_lines(self, isolated_log: Path) -> None:
        now = perf.time.time()
        isolated_log.write_text(
            "not-json\n"
            + json.dumps({"n": 1, "timestamp": now}) + "\n"
            + "{broken\n",
            encoding="utf-8",
        )
        result = perf.get_recent_stats(limit=10)
        assert result["count"] == 1
        assert result["stats"][0]["n"] == 1
