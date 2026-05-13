"""Tests for voice_session — WebSocket voice conversation loop."""
import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from gateway.voice_session import VoiceSession, _handle_text_message


class TestVoiceSession:
    def test_new_session_defaults(self):
        ws = MagicMock()
        session = VoiceSession(ws)
        assert session.mode == "ptt"
        assert session.messages == []
        assert session.turn_count == 0

    def test_add_user_message(self):
        ws = MagicMock()
        session = VoiceSession(ws)
        session.add_user_message("hello")
        assert len(session.messages) == 1
        assert session.messages[0] == {"role": "user", "content": "hello"}

    def test_add_assistant_message(self):
        ws = MagicMock()
        session = VoiceSession(ws)
        session.add_assistant_message("hi there")
        assert len(session.messages) == 1
        assert session.messages[0] == {"role": "assistant", "content": "hi there"}

    def test_message_history_maintains_order(self):
        ws = MagicMock()
        session = VoiceSession(ws)
        session.add_user_message("q1")
        session.add_assistant_message("a1")
        session.add_user_message("q2")
        session.add_assistant_message("a2")
        assert len(session.messages) == 4
        assert session.messages[0]["role"] == "user"
        assert session.messages[1]["role"] == "assistant"
        assert session.messages[2]["role"] == "user"
        assert session.messages[3]["role"] == "assistant"

    def test_trims_history_beyond_limit(self):
        ws = MagicMock()
        session = VoiceSession(ws)
        # MAX_MESSAGE_HISTORY = 20, fill beyond
        for i in range(25):
            session.add_user_message(f"msg{i}")
        assert len(session.messages) == 20
        assert session.messages[0]["content"] == "msg5"  # oldest kept
        assert session.messages[-1]["content"] == "msg24"  # newest kept

    def test_turn_count_increments(self):
        ws = MagicMock()
        session = VoiceSession(ws)
        session.turn_count += 1
        session.turn_count += 1
        assert session.turn_count == 2


@pytest.mark.asyncio
class TestHandleTextMessage:
    async def test_mode_switch(self):
        ws = AsyncMock()
        session = VoiceSession(ws)
        msg = json.dumps({"type": "mode", "mode": "vad"})
        await _handle_text_message(session, msg)
        assert session.mode == "vad"

    async def test_ping_pong(self):
        ws = AsyncMock()
        session = VoiceSession(ws)
        msg = json.dumps({"type": "ping"})
        await _handle_text_message(session, msg)
        ws.send_json.assert_called_once()
        sent = ws.send_json.call_args[0][0]
        assert sent["type"] == "pong"

    async def test_invalid_json_ignored(self):
        ws = AsyncMock()
        session = VoiceSession(ws)
        await _handle_text_message(session, "not json")
        ws.send_json.assert_not_called()

    async def test_unknown_type_ignored(self):
        ws = AsyncMock()
        session = VoiceSession(ws)
        msg = json.dumps({"type": "unknown_thing"})
        await _handle_text_message(session, msg)
        ws.send_json.assert_not_called()
