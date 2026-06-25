"""Tests for calendar — AppleScript bridge (mock-safe)."""

from unittest.mock import patch

from gateway.calendar_integration import (
    _parse_event_lines,
    _run_applescript,
    create,
    get_today,
    get_upcoming,
    get_upcoming_text,
    is_available,
)


class TestParseEvents:
    def test_parses_event_lines(self):
        output = "Meeting\n2026-05-13 10:00\n2026-05-13 11:00\nLunch\n2026-05-13 12:00\n2026-05-13 13:00"
        events = _parse_event_lines(output)
        assert len(events) == 2
        assert events[0]["title"] == "Meeting"
        assert events[0]["start"] == "2026-05-13 10:00"
        assert events[1]["title"] == "Lunch"

    def test_empty_output(self):
        assert _parse_event_lines("") == []
        assert _parse_event_lines("\n\n") == []


class TestApplescriptRunner:
    def test_success(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "ok"
            ok, out = _run_applescript("test")
            assert ok is True
            assert out == "ok"

    def test_failure(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 1
            mock_run.return_value.stderr = "error"
            ok, out = _run_applescript("test")
            assert ok is False

    def test_not_macos(self):
        with patch("subprocess.run", side_effect=FileNotFoundError):
            ok, out = _run_applescript("test")
            assert ok is False
            assert "not available" in out


class TestCalendarAPI:
    def test_get_today_mocked(self):
        with patch("gateway.calendar_integration._run_applescript") as mock_run:
            mock_run.return_value = (True, "Event\n2026-05-13 09:00\n2026-05-13 10:00")
            events = get_today()
            assert len(events) == 1

    def test_get_upcoming_mocked(self):
        with patch("gateway.calendar_integration._run_applescript") as mock_run:
            mock_run.return_value = (True, "Event\n2026-05-13 09:00\n2026-05-13 10:00")
            events = get_upcoming(3)
            assert len(events) == 1

    def test_create_mocked(self):
        with patch("gateway.calendar_integration._run_applescript") as mock_run:
            mock_run.return_value = (True, "")
            assert create("Test Event") is True

    def test_get_upcoming_text(self):
        with patch("gateway.calendar_integration.get_upcoming") as mock_get:
            mock_get.return_value = [
                {
                    "title": "Meeting",
                    "start": "2026-05-13 10:00",
                    "end": "2026-05-13 11:00",
                }
            ]
            text = get_upcoming_text()
            assert "Meeting" in text
            assert "## Upcoming Calendar Events" in text

    def test_is_available_mocked(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            assert is_available() is True
