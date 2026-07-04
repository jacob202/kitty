"""Tests for imessage — AppleScript bridge."""
from unittest.mock import patch

from gateway.imessage import is_available, read_recent, send


class TestSend:
    def test_sends_successfully(self):
        with patch("gateway.imessage._run_applescript") as mock:
            mock.return_value = (True, "")
            assert send("+1234567890", "hello") is True

    def test_handles_failure(self):
        with patch("gateway.imessage._run_applescript") as mock:
            mock.return_value = (False, "error")
            assert send("+1234567890", "hello") is False

    def test_targets_participant_not_buddy(self):
        with patch("gateway.imessage._run_applescript") as mock:
            mock.return_value = (True, "")
            send("+1234567890", "hello")
        script = mock.call_args[0][0]
        assert "participant" in script
        assert "buddy" not in script
        assert "service type = iMessage" in script

    def test_two_line_message_uses_real_linefeed_join_not_literal_backslash_n(self):
        with patch("gateway.imessage._run_applescript") as mock:
            mock.return_value = (True, "")
            send("+1234567890", "line one\nline two")
        script = mock.call_args[0][0]
        assert "\\n" not in script
        assert "& return &" in script
        assert '"line one"' in script
        assert '"line two"' in script


class TestReadRecent:
    def test_parses_messages(self):
        with patch("gateway.imessage._run_applescript") as mock:
            mock.return_value = (True, "Alice|||Hey there|||2026-05-13T10:00:00\nBob|||Hi|||2026-05-13T10:01:00")
            msgs = read_recent(5)
            assert len(msgs) == 2
            assert msgs[0]["sender"] == "Alice"
            assert msgs[0]["text"] == "Hey there"

    def test_empty_result(self):
        with patch("gateway.imessage._run_applescript") as mock:
            mock.return_value = (True, "")
            assert read_recent() == []


class TestIsAvailable:
    def test_available(self):
        with patch("subprocess.run") as mock:
            mock.return_value.returncode = 0
            assert is_available() is True

    def test_unavailable(self):
        with patch("subprocess.run", side_effect=FileNotFoundError):
            assert is_available() is False
