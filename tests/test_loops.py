"""Tests for gateway.loops — the loops substrate.

The route layer was slimmed in Phase 3 to a thin wrapper. These
tests pin the substrate: the 3 seed loops are real data, CRUD goes
through SQLite, and the route's "in-memory list" is gone.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from gateway import loops


@pytest.fixture
def isolated_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    db = tmp_path / "loops.db"
    monkeypatch.setattr(loops, "LOOPS_DB", db)
    return db


class TestSeed:
    def test_first_init_seeds_three_loops(
        self, isolated_db: Path
    ) -> None:
        rows = loops.list_loops()
        ids = {row["loop_id"] for row in rows}
        assert ids == {"daily-brief", "search-index", "memory-consolidation"}

    def test_seed_preserves_statuses(
        self, isolated_db: Path
    ) -> None:
        rows = loops.list_loops()
        by_id = {r["loop_id"]: r for r in rows}
        assert by_id["daily-brief"]["status"] == "running"
        assert by_id["search-index"]["status"] == "running"
        assert by_id["memory-consolidation"]["status"] == "paused"

    def test_seed_preserves_intervals(
        self, isolated_db: Path
    ) -> None:
        rows = loops.list_loops()
        by_id = {r["loop_id"]: r for r in rows}
        assert by_id["daily-brief"]["interval_minutes"] == 1440
        assert by_id["search-index"]["interval_minutes"] == 15
        assert by_id["memory-consolidation"]["interval_minutes"] == 360

    def test_second_init_does_not_duplicate(
        self, isolated_db: Path
    ) -> None:
        loops.list_loops()  # first init seeds
        loops.init_db()  # second init must be a no-op
        rows = loops.list_loops()
        assert len(rows) == 3


class TestCreateLoop:
    def test_adds_one_row(self, isolated_db: Path) -> None:
        loop = loops.create_loop({"name": "My Loop", "interval_minutes": 30})
        assert loop["name"] == "My Loop"
        assert loop["interval_minutes"] == 30
        assert loop["status"] == "idle"
        assert loop["loop_id"] == "my-loop"
        rows = loops.list_loops()
        assert len(rows) == 4  # 3 seed + 1 new

    def test_collisions_get_a_suffix(
        self, isolated_db: Path
    ) -> None:
        first = loops.create_loop({"name": "Daily Brief"})
        second = loops.create_loop({"name": "Daily Brief"})
        # The seed already owns "daily-brief", so the first new row is
        # "daily-brief-1" and the second is "daily-brief-2".
        assert first["loop_id"] == "daily-brief-1"
        assert second["loop_id"] == "daily-brief-2"
        assert first["loop_id"] != second["loop_id"]
        rows = {r["loop_id"] for r in loops.list_loops()}
        assert rows == {"daily-brief", "daily-brief-1", "daily-brief-2",
                        "search-index", "memory-consolidation"}

    def test_rejects_empty_name(self, isolated_db: Path) -> None:
        with pytest.raises(ValueError, match="name"):
            loops.create_loop({})

    def test_rejects_non_dict(self, isolated_db: Path) -> None:
        with pytest.raises(TypeError, match="loop spec must be a dict"):
            loops.create_loop("nope")  # type: ignore[arg-type]


class TestToggle:
    def test_running_becomes_paused(self, isolated_db: Path) -> None:
        updated = loops.toggle_loop("daily-brief")
        assert updated is not None
        assert updated["status"] == "paused"

    def test_paused_becomes_running(self, isolated_db: Path) -> None:
        loops.toggle_loop("daily-brief")  # running -> paused
        updated = loops.toggle_loop("daily-brief")
        assert updated is not None
        assert updated["status"] == "running"

    def test_unknown_id_returns_none(self, isolated_db: Path) -> None:
        assert loops.toggle_loop("ghost-loop") is None

    def test_updates_timestamp(self, isolated_db: Path) -> None:
        before = loops.list_loops()
        before_ts = next(r for r in before if r["loop_id"] == "search-index")["updated_at"]
        loops.toggle_loop("search-index")
        after_ts = next(r for r in loops.list_loops() if r["loop_id"] == "search-index")["updated_at"]
        assert after_ts >= before_ts

    def test_rejects_empty_id(self, isolated_db: Path) -> None:
        with pytest.raises(ValueError, match="loop_id"):
            loops.toggle_loop("")


class TestDelete:
    def test_removes_named_loop(self, isolated_db: Path) -> None:
        assert loops.delete_loop("search-index") is True
        ids = {r["loop_id"] for r in loops.list_loops()}
        assert "search-index" not in ids
        assert len(ids) == 2

    def test_unknown_id_returns_false(self, isolated_db: Path) -> None:
        assert loops.delete_loop("ghost-loop") is False

    def test_rejects_empty_id(self, isolated_db: Path) -> None:
        with pytest.raises(ValueError, match="loop_id"):
            loops.delete_loop("")
