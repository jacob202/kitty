"""Tests for web_monitor — URL watching and keyword matching."""
from unittest.mock import AsyncMock, patch

import pytest

from gateway.web_monitor import add_watch, init_db, list_watches, remove_watch


class TestCRUD:
    def test_add_and_list(self):
        with patch("gateway.web_monitor._ensure_polling"):
            watch_id = add_watch("https://example.com", label="test")
        assert isinstance(watch_id, str)
        assert len(watch_id) == 8

        watches = list_watches()
        assert any(w["url"] == "https://example.com" for w in watches)

    def test_remove(self):
        with patch("gateway.web_monitor._ensure_polling"):
            wid = add_watch("https://example.com/remove-test")
        assert remove_watch(wid) is True
        assert remove_watch(wid) is False  # already removed

    def test_remove_nonexistent(self):
        assert remove_watch("nonexistent") is False

    def test_keywords_stored(self):
        with patch("gateway.web_monitor._ensure_polling"):
            wid = add_watch("https://example.com", keywords=["sansui", "bias"])
        watches = list_watches()
        match = [w for w in watches if w["id"] == wid]
        assert len(match) == 1
        assert "sansui" in match[0]["keywords"]


class TestCheck:
    @pytest.mark.asyncio
    async def test_check_no_change_first_time(self):
        with patch("gateway.web_monitor._ensure_polling"):
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
        with patch("gateway.web_monitor._ensure_polling"):
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
    async def test_keyword_match_counts_as_change(self):
        with patch("gateway.web_monitor._ensure_polling"):
            wid = add_watch("https://example.com/test3", keywords=["sansui"])

        with patch("httpx.AsyncClient.get") as mock_get:
            mock_resp = AsyncMock()
            mock_resp.status_code = 200
            mock_resp.text = "found a Sansui AU-7900 for sale"
            mock_get.return_value = mock_resp
            from gateway.web_monitor import check_now
            result = await check_now(wid)
            assert result.get("changed") is True
            assert "sansui" in result.get("keyword_matches", [])


class TestDB:
    def test_init_idempotent(self):
        init_db()
        init_db()
