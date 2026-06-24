"""Tests for gateway.monitors — the monitors substrate.

The route layer was slimmed in Phase 3 to a thin wrapper. These
tests pin the substrate: the module delegates to ``web_monitor``
and never returns an in-memory mock.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from gateway import monitors


@pytest.fixture
def isolated_watch_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    from gateway import web_monitor

    db = tmp_path / "web_monitors.db"
    monkeypatch.setattr(web_monitor, "MONITOR_DB", db)
    return db


class TestListMonitors:
    def test_empty_initially(self, isolated_watch_db: Path) -> None:
        assert monitors.list_monitors() == []

    def test_returns_watches_after_add(self, isolated_watch_db: Path) -> None:
        from gateway import web_monitor

        with patch.object(web_monitor, "_ensure_polling"):
            web_monitor.add_watch("https://example.com", label="example")
        rows = monitors.list_monitors()
        assert any(r["url"] == "https://example.com" for r in rows)


class TestCreateMonitor:
    def test_returns_watch_dict(self, isolated_watch_db: Path) -> None:
        from gateway import web_monitor

        with patch.object(web_monitor, "_ensure_polling"):
            watch = monitors.create_monitor("https://example.com/x", interval_minutes=120)
        assert watch["url"] == "https://example.com/x"
        assert watch["interval"] == 120
        assert watch["enabled"] is True
        assert isinstance(watch["watch_id"], str)
        assert len(watch["watch_id"]) == 8

    def test_validates_url(self, isolated_watch_db: Path) -> None:
        with pytest.raises(ValueError, match="url"):
            monitors.create_monitor("", interval_minutes=60)
        with pytest.raises(ValueError, match="url"):
            monitors.create_monitor(123, interval_minutes=60)  # type: ignore[arg-type]

    def test_validates_interval(self, isolated_watch_db: Path) -> None:
        with pytest.raises(ValueError, match="interval_minutes"):
            monitors.create_monitor("https://example.com", interval_minutes=0)
        with pytest.raises(ValueError, match="interval_minutes"):
            monitors.create_monitor("https://example.com", interval_minutes=-1)


class TestDeleteMonitor:
    def test_returns_true_for_existing(
        self, isolated_watch_db: Path
    ) -> None:
        from gateway import web_monitor

        with patch.object(web_monitor, "_ensure_polling"):
            wid = web_monitor.add_watch("https://example.com/del")
        assert monitors.delete_monitor(wid) is True

    def test_returns_false_for_unknown(
        self, isolated_watch_db: Path
    ) -> None:
        assert monitors.delete_monitor("nope") is False

    def test_validates_id(self, isolated_watch_db: Path) -> None:
        with pytest.raises(ValueError, match="monitor_id"):
            monitors.delete_monitor("")
        with pytest.raises(ValueError, match="monitor_id"):
            monitors.delete_monitor(42)  # type: ignore[arg-type]


class TestCheckMonitor:
    @pytest.mark.asyncio
    async def test_returns_check_result(
        self, isolated_watch_db: Path
    ) -> None:
        from gateway import web_monitor

        with patch.object(web_monitor, "_ensure_polling"):
            wid = web_monitor.add_watch("https://example.com/check")
        with patch.object(web_monitor, "check_now", return_value={"watch_id": wid, "changed": False}) as mock_check:
            result = await monitors.check_monitor(wid)
        assert result["watch_id"] == wid
        mock_check.assert_awaited_once_with(wid)

    @pytest.mark.asyncio
    async def test_validates_id(self, isolated_watch_db: Path) -> None:
        with pytest.raises(ValueError, match="monitor_id"):
            await monitors.check_monitor("")
