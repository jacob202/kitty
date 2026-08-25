"""Tests for web_monitor — URL watching and keyword matching."""
from unittest.mock import AsyncMock, patch

import pytest

from gateway.web_monitor import add_watch, init_db, list_watches, remove_watch


class TestCRUD:
    def test_add_and_list(self):
        watch_id = add_watch("https://example.com", label="test")
        assert isinstance(watch_id, str)
        assert len(watch_id) == 8

        watches = list_watches()
        assert any(w["url"] == "https://example.com" for w in watches)

    def test_remove(self):
        wid = add_watch("https://example.com/remove-test")
        assert remove_watch(wid) is True
        assert remove_watch(wid) is False  # already removed

    def test_remove_nonexistent(self):
        assert remove_watch("nonexistent") is False

    def test_keywords_stored(self):
        wid = add_watch("https://example.com", keywords=["sansui", "bias"])
        watches = list_watches()
        match = [w for w in watches if w["id"] == wid]
        assert len(match) == 1
        assert "sansui" in match[0]["keywords"]


class TestCheck:
    @pytest.mark.asyncio
    async def test_check_no_change_first_time(self):
        wid = add_watch("https://example.com/test1")

        with patch("httpx.AsyncClient.get") as mock_get:
            mock_resp = AsyncMock()
            mock_resp.status_code = 200
            mock_resp.text = "initial content"
            mock_get.return_value = mock_resp

            from gateway.web_monitor import check_now
            result = await check_now(wid)
            assert result.get("changed") is False  # first check, no previous hash

    @pytest.mark.asyncio
    async def test_check_detects_change(self):
        wid = add_watch("https://example.com/test2")

        # First check — set initial hash
        with patch("httpx.AsyncClient.get") as mock_get:
            mock_resp = AsyncMock()
            mock_resp.status_code = 200
            mock_resp.text = "version 1"
            mock_get.return_value = mock_resp
            from gateway.web_monitor import check_now
            await check_now(wid)

        # Second check — different content
        with patch("httpx.AsyncClient.get") as mock_get:
            mock_resp = AsyncMock()
            mock_resp.status_code = 200
            mock_resp.text = "version 2"
            mock_get.return_value = mock_resp
            result = await check_now(wid)
            assert result.get("changed") is True

    @pytest.mark.asyncio
    async def test_keyword_match_on_first_check_does_not_count_as_change(self):
        """RC-09: the first-ever check has no baseline to transition from, so
        it must not report a change — same guard non-keyword watches already
        had via test_check_no_change_first_time. keyword_matches still
        reports the match for visibility."""
        wid = add_watch("https://example.com/test3", keywords=["sansui"])

        with patch("httpx.AsyncClient.get") as mock_get:
            mock_resp = AsyncMock()
            mock_resp.status_code = 200
            mock_resp.text = "found a Sansui AU-7900 for sale"
            mock_get.return_value = mock_resp
            from gateway.web_monitor import check_now
            result = await check_now(wid)
            assert result.get("changed") is False
            assert "sansui" in result.get("keyword_matches", [])

    @pytest.mark.asyncio
    async def test_keyword_match_transition_counts_as_change(self):
        """The false -> true match transition (only) counts as a change."""
        wid = add_watch("https://example.com/test3b", keywords=["sansui"])
        from gateway.web_monitor import check_now

        with patch("httpx.AsyncClient.get") as mock_get:
            mock_resp = AsyncMock()
            mock_resp.status_code = 200
            mock_resp.text = "nothing interesting here"
            mock_get.return_value = mock_resp
            baseline = await check_now(wid)
            assert baseline.get("changed") is False

        with patch("httpx.AsyncClient.get") as mock_get:
            mock_resp = AsyncMock()
            mock_resp.status_code = 200
            mock_resp.text = "found a Sansui AU-7900 for sale"
            mock_get.return_value = mock_resp
            result = await check_now(wid)
            assert result.get("changed") is True
            assert "sansui" in result.get("keyword_matches", [])


class TestDB:
    def test_init_idempotent(self):
        init_db()
        init_db()


@pytest.mark.asyncio
async def test_check_due_preserves_per_watch_intervals(monkeypatch):
    import gateway.web_monitor as wm

    now = 1_000.0
    watches = [
        {"id": "due", "enabled": True, "interval_minutes": 5, "last_checked": 600.0},
        {"id": "early", "enabled": True, "interval_minutes": 5, "last_checked": 900.0},
        {"id": "off", "enabled": False, "interval_minutes": 1, "last_checked": 0.0},
    ]
    monkeypatch.setattr(wm, "list_watches", lambda: watches)
    monkeypatch.setattr(wm.time, "time", lambda: now)

    checked: list[str] = []
    handled: list[str] = []

    async def fake_check(watch):
        checked.append(watch["id"])
        return {"changed": True}

    async def fake_handle(watch, _result):
        handled.append(watch["id"])

    async def no_sleep(_seconds):
        return None

    monkeypatch.setattr(wm, "_check_watch", fake_check)
    monkeypatch.setattr(wm, "_handle_watch_result", fake_handle)
    monkeypatch.setattr(wm.asyncio, "sleep", no_sleep)

    result = await wm.check_due()

    assert checked == ["due"]
    assert handled == ["due"]
    assert result == {"checked": 1, "changed": 1, "failed": 0}
