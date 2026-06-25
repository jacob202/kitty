"""Tests for telegram_bot — polling, message sending, commands."""
from unittest.mock import AsyncMock, patch

import pytest

from gateway.telegram_bot import (
    _handle_command,
    is_configured,
    send_message,
)


class TestConfigured:
    def test_not_configured_without_token(self):
        with patch.dict("os.environ", {}, clear=True):
            # Need to reload the module's TOKEN
            import gateway.telegram_bot as tb
            tb.TOKEN = ""
            assert is_configured() is False

    def test_configured_with_token(self):
        with patch.dict("os.environ", {"TELEGRAM_BOT_TOKEN": "test123"}, clear=True):
            import gateway.telegram_bot as tb
            tb.TOKEN = "test123"
            assert is_configured() is True


class TestSendMessage:
    @pytest.mark.asyncio
    async def test_skips_without_token(self):
        import gateway.telegram_bot as tb
        tb.TOKEN = ""
        assert await send_message(123, "test") is False

    @pytest.mark.asyncio
    async def test_sends_with_token(self):
        import gateway.telegram_bot as tb
        tb.TOKEN = "fake"
        with patch("httpx.AsyncClient.post") as mock_post:
            mock_resp = AsyncMock()
            mock_resp.status_code = 200
            mock_post.return_value = mock_resp
            assert await send_message(123, "hello") is True

    @pytest.mark.asyncio
    async def test_fallback_without_markdown(self):
        import gateway.telegram_bot as tb
        tb.TOKEN = "fake"
        with patch("httpx.AsyncClient.post") as mock_post:
            mock_resp_bad = AsyncMock()
            mock_resp_bad.status_code = 400
            mock_resp_bad.text = "can't parse entities"
            mock_resp_ok = AsyncMock()
            mock_resp_ok.status_code = 200
            mock_post.side_effect = [mock_resp_bad, mock_resp_ok]
            assert await send_message(123, "*bold*") is True
            assert mock_post.call_count == 2


@pytest.mark.asyncio
class TestCommands:
    async def test_help(self):
        import gateway.telegram_bot as tb
        tb.TOKEN = "fake"
        with patch("gateway.telegram_bot.send_message", new=AsyncMock(return_value=True)):
            await _handle_command(123, "/help")

    async def test_start(self):
        import gateway.telegram_bot as tb
        tb.TOKEN = "fake"
        with patch("gateway.telegram_bot.send_message", new=AsyncMock(return_value=True)):
            await _handle_command(123, "/start")
