"""Tests for gateway.life_awareness — calendar-aware, do-not-disturb, proactive life companion."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from gateway import life_awareness


@pytest.fixture(autouse=True)
def clear_caches():
    life_awareness.invalidate_caches()
    yield
    life_awareness.invalidate_caches()


class TestMeetingDetection:
    def test_am_in_meeting_true_when_event_is_now(self):
        now = time.time()
        events = [
            {"title": "Standup", "start": datetime.fromtimestamp(now - 300, tz=timezone.utc).isoformat(),
             "end": datetime.fromtimestamp(now + 300, tz=timezone.utc).isoformat()},
        ]
        assert life_awareness._is_in_meeting(events) is True

    def test_am_in_meeting_false_when_no_events(self):
        assert life_awareness._is_in_meeting([]) is False

    def test_am_in_meeting_false_when_event_is_past(self):
        time.time()
        events = [
            {"title": "Old event", "start": "2020-01-01T09:00:00", "end": "2020-01-01T10:00:00"},
        ]
        assert life_awareness._is_in_meeting(events) is False

    def test_current_meeting_returns_event_when_in_meeting(self):
        now = time.time()
        expected = {"title": "Standup", "start": datetime.fromtimestamp(now - 300, tz=timezone.utc).isoformat(),
                     "end": datetime.fromtimestamp(now + 300, tz=timezone.utc).isoformat()}
        with patch.object(life_awareness, "today_events", return_value=[expected]):
            meeting = life_awareness.current_meeting()
        assert meeting is not None
        assert meeting["title"] == "Standup"

    def test_current_meeting_returns_none_when_free(self):
        with patch.object(life_awareness, "today_events", return_value=[]):
            meeting = life_awareness.current_meeting()
        assert meeting is None


class TestDoNotDisturb:
    def test_dnd_false_when_no_meeting(self):
        with patch.object(life_awareness, "today_events", return_value=[]):
            status = life_awareness.do_not_disturb_status()
        assert status["do_not_disturb"] is False
        assert status["in_meeting"] is False
        assert "calendar_source" in status
        assert "available" in status["calendar_source"]
        assert "state" in status["calendar_source"]

    def test_dnd_true_during_meeting(self):
        now = time.time()
        events = [
            {"title": "Sprint Review", "start": datetime.fromtimestamp(now - 600, tz=timezone.utc).isoformat(),
             "end": datetime.fromtimestamp(now + 600, tz=timezone.utc).isoformat()},
        ]
        with patch.object(life_awareness, "today_events", return_value=events):
            status = life_awareness.do_not_disturb_status()
        assert status["do_not_disturb"] is True
        assert status["in_meeting"] is True

    def test_dnd_caches_result(self):
        with patch.object(life_awareness, "today_events", return_value=[]) as mock:
            life_awareness.do_not_disturb_status()
            life_awareness.do_not_disturb_status()
        mock.assert_called_once()

    def test_invalidate_dnd_cache_forces_refresh(self):
        with patch.object(life_awareness, "today_events", return_value=[]) as mock:
            life_awareness.do_not_disturb_status()
            life_awareness.invalidate_caches()
            life_awareness.do_not_disturb_status()
        assert mock.call_count == 2


class TestMeetingBlockText:
    def test_returns_none_when_free(self):
        with patch.object(life_awareness, "do_not_disturb_status", return_value={
            "do_not_disturb": False, "in_meeting": False,
        }):
            assert life_awareness.meeting_block_text() is None

    def test_returns_block_during_meeting(self):
        with patch.object(life_awareness, "do_not_disturb_status", return_value={
            "do_not_disturb": True,
            "in_meeting": True,
            "current_meeting": {"title": "1:1"},
            "next_free": {"after": "1:1", "free_at": "10:30"},
        }):
            text = life_awareness.meeting_block_text()
        assert text is not None
        assert "DO NOT DISTURB" in text
        assert "1:1" in text


class TestTodayEvents:
    def test_today_events_returns_list(self):
        with patch("gateway.calendar_integration.is_available", return_value=True), \
             patch("gateway.calendar_integration.get_today", return_value=[
                 {"title": "Standup", "start": "9:00", "end": "9:30"},
             ]):
            events = life_awareness.today_events()
        assert len(events) == 1
        assert events[0]["title"] == "Standup"

    def test_today_events_empty_when_unavailable(self):
        with patch("gateway.calendar_integration.is_available", return_value=False):
            events = life_awareness.today_events()
        assert events == []


class TestYesterdayRecap:
    def test_yesterday_recap_returns_dict(self):
        with patch.object(life_awareness, "_yesterday_signals", return_value=[]), \
             patch.object(life_awareness, "_yesterday_journal", return_value=[]):
            recap = life_awareness.yesterday_recap()
        assert "signal_count" in recap
        assert "journal_count" in recap
        assert "has_data" in recap
        assert recap["has_data"] is False

    def test_yesterday_recap_caches(self):
        with patch.object(life_awareness, "_yesterday_signals", return_value=[]) as mock:
            life_awareness.yesterday_recap()
            life_awareness.yesterday_recap()
        mock.assert_called_once()

    def test_yesterday_with_data(self):
        with patch.object(life_awareness, "_yesterday_signals", return_value=[
            {"ts": time.time() - 1000, "source": "test", "kind": "test", "payload": {}},
        ]), patch.object(life_awareness, "_yesterday_journal", return_value=[
            {"ts": time.time() - 1000, "entry": "wrote some code"},
        ]):
            recap = life_awareness.yesterday_recap()
        assert recap["has_data"] is True
        assert recap["signal_count"] == 1
        assert recap["journal_count"] == 1


class TestMorningProactive:
    def test_morning_proactive_returns_structure(self):
        with patch.object(life_awareness, "today_events", return_value=[]), \
             patch.object(life_awareness, "_life_project_steps_today", return_value=[]), \
             patch.object(life_awareness, "yesterday_recap", return_value={
                 "has_data": False, "signal_count": 0, "journal_count": 0,
             }):
            result = life_awareness.morning_proactive()
        assert "now" in result
        assert "events" in result
        assert "life_steps" in result
        assert "proactive_suggestions" in result
        assert isinstance(result["proactive_suggestions"], list)
        assert "calendar_source" in result
        assert "available" in result["calendar_source"]
        assert "state" in result["calendar_source"]

    def test_proactive_with_life_steps(self):
        with patch.object(life_awareness, "today_events", return_value=[]), \
             patch.object(life_awareness, "_life_project_steps_today", return_value=[
                 {"project_name": "Job Search", "step": "Update resume",
                  "why": "Application deadline", "project_id": 1},
             ]), \
             patch.object(life_awareness, "yesterday_recap", return_value={
                 "has_data": False, "signal_count": 0, "journal_count": 0,
             }):
            result = life_awareness.morning_proactive()
        suggestions = result["proactive_suggestions"]
        assert any(s["kind"] == "life_step" for s in suggestions)
        assert any("Job Search" in s["text"] for s in suggestions)


class TestEveningReflection:
    def test_evening_reflection_returns_structure(self):
        with patch.object(life_awareness, "today_events", return_value=[]), \
             patch.object(life_awareness, "_life_project_steps_today", return_value=[]):
            result = life_awareness.evening_reflection()
        assert "reflection" in result
        assert "events" in result
        assert "event_count" in result

    def test_evening_reflection_caches(self):
        with patch.object(life_awareness, "today_events", return_value=[]) as mock, \
             patch.object(life_awareness, "_life_project_steps_today", return_value=[]), \
             patch.object(life_awareness, "generate_evening_reflection_text", return_value="reflection"):
            life_awareness.evening_reflection()
            life_awareness.evening_reflection()
        mock.assert_called_once()


class TestGenerateText:
    def test_generate_evening_reflection_fallback(self):
        with patch("gateway.llm_client.call_llm", side_effect=Exception("LLM down")):
            text = life_awareness.generate_evening_reflection_text()
        assert isinstance(text, str)
        assert len(text) > 0

    def test_generate_proactive_fallback(self):
        with patch("gateway.llm_client.call_llm", side_effect=Exception("LLM down")):
            text = life_awareness.generate_proactive_text()
        assert isinstance(text, str)
        assert len(text) > 0

    def test_generate_evening_reflection_llm_path(self):
        fake_text = "Good evening, Jacob. Today was productive."
        with patch("gateway.llm_client.call_llm", return_value=fake_text):
            text = life_awareness.generate_evening_reflection_text()
        assert text == fake_text

    def test_generate_proactive_llm_path(self):
        fake_text = "Morning, Jacob. Focus on that resume update today."
        with patch("gateway.llm_client.call_llm", return_value=fake_text):
            text = life_awareness.generate_proactive_text()
        assert text == fake_text


class TestBuildProactiveSuggestions:
    def test_life_step_suggestions_included(self):
        steps = [{"project_name": "Job Search", "step": "Update resume", "why": "deadline", "project_id": 1}]
        suggestions = life_awareness._build_proactive_suggestions([], steps, {"has_data": False, "signal_count": 0, "journal_count": 0})
        kinds = [s["kind"] for s in suggestions]
        assert "life_step" in kinds

    def test_upcoming_event_suggestion(self):
        now = time.time()
        events = [{
            "title": "Standup",
            "start": datetime.fromtimestamp(now + 3600, tz=timezone.utc).isoformat(),
            "end": datetime.fromtimestamp(now + 5400, tz=timezone.utc).isoformat(),
        }]
        suggestions = life_awareness._build_proactive_suggestions(events, [], {"has_data": False, "signal_count": 0, "journal_count": 0})
        kinds = [s["kind"] for s in suggestions]
        assert "upcoming_event" in kinds

    def test_journal_suggestion_when_entries(self):
        suggestions = life_awareness._build_proactive_suggestions([], [], {"has_data": True, "signal_count": 0, "journal_count": 3})
        kinds = [s["kind"] for s in suggestions]
        assert "journal_reflection" in kinds

    def test_focus_block_during_meeting(self):
        now = time.time()
        events = [{"title": "Meeting", "start": datetime.fromtimestamp(now - 300, tz=timezone.utc).isoformat(),
                    "end": datetime.fromtimestamp(now + 300, tz=timezone.utc).isoformat()}]
        suggestions = life_awareness._build_proactive_suggestions(events, [], {"has_data": False, "signal_count": 0, "journal_count": 0})
        kinds = [s["kind"] for s in suggestions]
        assert "focus_block" in kinds


class TestEmitLifeSignal:
    def test_emit_life_signal_returns_none_on_failure(self):
        with patch("gateway.signal_store.emit", side_effect=Exception("db error")):
            result = life_awareness.emit_life_signal("test", {})
        assert result is None

    def test_emit_meeting_detected(self):
        with patch("gateway.signal_store.emit", return_value={"id": 1}) as mock:
            life_awareness.emit_life_signal(life_awareness.MEETING_DETECTED, {"title": "Standup"})
        mock.assert_called_once()


class TestTodaySummary:
    def test_today_summary_structure(self):
        with patch.object(life_awareness, "today_events", return_value=[]), \
             patch.object(life_awareness, "_life_project_steps_today", return_value=[]):
            summary = life_awareness.today_summary()
        assert "now" in summary
        assert "event_count" in summary
        assert "in_meeting" in summary
        assert summary["in_meeting"] is False
        assert "calendar_source" in summary
        assert "available" in summary["calendar_source"]
        assert "state" in summary["calendar_source"]


class TestFallbackText:
    def test_fallback_reflection_includes_events(self):
        events = [{"title": "Standup", "start": "9:00", "end": "9:30"}]
        text = life_awareness._fallback_reflection(events, [])
        assert "Standup" in text

    def test_fallback_proactive_includes_steps(self):
        steps = [{"project_name": "Job Search", "step": "Update resume", "why": "", "project_id": 1}]
        text = life_awareness._fallback_proactive([], steps)
        assert "Job Search" in text


class TestMeetingBlockTextIntegration:
    def test_meeting_block_text_in_context_enrichment(self):
        from gateway import context_enrichment
        assert any("meeting" in fn.__name__ for fn in context_enrichment._ENRICHMENTS)


class TestLifeRoutesContract:
    """Route integration tests using TestClient against just the life router.

    Uses a mini FastAPI app scoped to the life router only — no background
    tasks, no cron, no full app startup.
    """

    @pytest.fixture
    def client(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from gateway.routes.life import router

        app = FastAPI()
        app.include_router(router)
        return TestClient(app)

    def test_life_check_endpoint(self, client):
        with patch.object(life_awareness, "today_events", return_value=[]), \
             patch.object(life_awareness, "_life_project_steps_today", return_value=[]), \
             patch.object(life_awareness, "_yesterday_signals", return_value=[]), \
             patch.object(life_awareness, "_yesterday_journal", return_value=[]):
            resp = client.get("/life/check")
        assert resp.status_code == 200
        data = resp.json()
        assert "do_not_disturb" in data
        assert "in_meeting" in data
        assert "life_step_count" in data

    def test_life_today_endpoint(self, client):
        with patch.object(life_awareness, "today_events", return_value=[]), \
             patch.object(life_awareness, "_life_project_steps_today", return_value=[]):
            resp = client.get("/life/today")
        assert resp.status_code == 200

    def test_life_dnd_endpoint(self, client):
        with patch.object(life_awareness, "today_events", return_value=[]):
            resp = client.get("/life/dnd")
        assert resp.status_code == 200

    def test_life_proactive_endpoint(self, client):
        with patch.object(life_awareness, "today_events", return_value=[]), \
             patch.object(life_awareness, "_life_project_steps_today", return_value=[]), \
             patch.object(life_awareness, "yesterday_recap", return_value={
                 "has_data": False, "signal_count": 0, "journal_count": 0,
             }):
            resp = client.get("/life/proactive")
        assert resp.status_code == 200

    def test_life_reflection_endpoint(self, client):
        with patch.object(life_awareness, "today_events", return_value=[]), \
             patch.object(life_awareness, "_life_project_steps_today", return_value=[]):
            resp = client.get("/life/reflection")
        assert resp.status_code == 200

    def test_life_meeting_endpoint_when_free(self, client):
        with patch.object(life_awareness, "today_events", return_value=[]):
            resp = client.get("/life/meeting")
        assert resp.status_code == 200
        assert resp.json()["in_meeting"] is False

    def test_life_yesterday_endpoint(self, client):
        with patch.object(life_awareness, "_yesterday_signals", return_value=[]), \
             patch.object(life_awareness, "_yesterday_journal", return_value=[]):
            resp = client.get("/life/yesterday")
        assert resp.status_code == 200

    def test_life_reflection_generate(self, client):
        with patch.object(life_awareness, "generate_evening_reflection_text", return_value="reflection"), \
             patch.object(life_awareness, "emit_life_signal", return_value=None):
            resp = client.post("/life/reflection/generate")
        assert resp.status_code == 200
        assert resp.json()["reflection"] == "reflection"

    def test_life_proactive_generate(self, client):
        with patch.object(life_awareness, "generate_proactive_text", return_value="proactive"), \
             patch.object(life_awareness, "emit_life_signal", return_value=None):
            resp = client.post("/life/proactive/generate")
        assert resp.status_code == 200
        assert resp.json()["proactive"] == "proactive"

    def test_life_cache_invalidate(self, client):
        resp = client.post("/life/cache/invalidate")
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    def test_life_dismiss(self, client):
        with patch.object(life_awareness, "emit_life_signal", return_value=None):
            resp = client.post("/life/dismiss/test_signal")
        assert resp.status_code == 200
        assert resp.json()["dismissed"] == "test_signal"

    def test_life_events_endpoint(self, client):

        with patch("gateway.signal_store.list_recent", return_value=[
            {"source": "life_awareness", "kind": "test", "ts": 1000.0, "payload": {}, "id": 1},
        ]):
            resp = client.get("/life/events?limit=5")
        assert resp.status_code == 200

    def test_life_meeting_when_in_meeting(self, client):
        now = time.time()
        meeting = {"title": "1:1", "start": datetime.fromtimestamp(now - 300, tz=timezone.utc).isoformat(),
                    "end": datetime.fromtimestamp(now + 300, tz=timezone.utc).isoformat()}
        with patch.object(life_awareness, "today_events", return_value=[meeting]):
            resp = client.get("/life/meeting")
        assert resp.status_code == 200
        assert resp.json()["in_meeting"] is True
        assert resp.json()["meeting"]["title"] == "1:1"

    def test_life_check_carries_calendar_source(self, client):
        with patch("gateway.calendar_integration.is_available", return_value=True), \
             patch.object(life_awareness, "today_events", return_value=[]), \
             patch.object(life_awareness, "_life_project_steps_today", return_value=[]), \
             patch.object(life_awareness, "_yesterday_signals", return_value=[]), \
             patch.object(life_awareness, "_yesterday_journal", return_value=[]):
            resp = client.get("/life/check")
        assert resp.status_code == 200
        data = resp.json()
        assert "calendar_source" in data
        assert data["calendar_source"]["available"] is True
        assert data["calendar_source"]["state"] == "healthy"


class TestCalendarSource:
    """Calendar availability seam: projections carry source-health metadata."""

    def test_calendar_source_healthy_when_available(self):
        with patch("gateway.calendar_integration.is_available", return_value=True):
            source = life_awareness._calendar_source_state()
        assert source["available"] is True
        assert source["state"] == "healthy"

    def test_calendar_source_unavailable_when_integration_absent(self):
        with patch("gateway.calendar_integration.is_available", return_value=False):
            source = life_awareness._calendar_source_state()
        assert source["available"] is False
        assert source["state"] == "unavailable"

    def test_calendar_source_unavailable_on_import_error(self):
        with patch("gateway.calendar_integration.is_available", side_effect=ImportError("no calendar")):
            source = life_awareness._calendar_source_state()
        assert source["available"] is False
        assert source["state"] == "unavailable"

    def test_today_summary_available_no_events_reports_healthy(self):
        with patch("gateway.calendar_integration.is_available", return_value=True), \
             patch.object(life_awareness, "today_events", return_value=[]), \
             patch.object(life_awareness, "_life_project_steps_today", return_value=[]):
            summary = life_awareness.today_summary()
        assert summary["event_count"] == 0
        assert summary["calendar_source"]["available"] is True
        assert summary["calendar_source"]["state"] == "healthy"

    def test_today_summary_unavailable_reports_source_state(self):
        with patch("gateway.calendar_integration.is_available", return_value=False), \
             patch.object(life_awareness, "today_events", return_value=[]), \
             patch.object(life_awareness, "_life_project_steps_today", return_value=[]):
            summary = life_awareness.today_summary()
        assert summary["calendar_source"]["available"] is False
        assert summary["calendar_source"]["state"] == "unavailable"

    def test_dnd_calendar_source_available(self):
        with patch("gateway.calendar_integration.is_available", return_value=True), \
             patch.object(life_awareness, "today_events", return_value=[]):
            status = life_awareness.do_not_disturb_status()
        assert status["calendar_source"]["available"] is True
        assert status["calendar_source"]["state"] == "healthy"

    def test_dnd_calendar_source_unavailable(self):
        with patch("gateway.calendar_integration.is_available", return_value=False), \
             patch.object(life_awareness, "today_events", return_value=[]):
            status = life_awareness.do_not_disturb_status()
        assert status["calendar_source"]["available"] is False
        assert status["calendar_source"]["state"] == "unavailable"

    def test_proactive_calendar_source_available(self):
        with patch("gateway.calendar_integration.is_available", return_value=True), \
             patch.object(life_awareness, "today_events", return_value=[]), \
             patch.object(life_awareness, "_life_project_steps_today", return_value=[]), \
             patch.object(life_awareness, "yesterday_recap", return_value={
                 "has_data": False, "signal_count": 0, "journal_count": 0,
             }):
            result = life_awareness.morning_proactive()
        assert result["calendar_source"]["available"] is True
        assert result["calendar_source"]["state"] == "healthy"

    def test_proactive_calendar_source_unavailable(self):
        with patch("gateway.calendar_integration.is_available", return_value=False), \
             patch.object(life_awareness, "today_events", return_value=[]), \
             patch.object(life_awareness, "_life_project_steps_today", return_value=[]), \
             patch.object(life_awareness, "yesterday_recap", return_value={
                 "has_data": False, "signal_count": 0, "journal_count": 0,
             }):
            result = life_awareness.morning_proactive()
        assert result["calendar_source"]["available"] is False
        assert result["calendar_source"]["state"] == "unavailable"

    def test_today_events_still_returns_list(self):
        """today_events() compatibility API must always return a list."""
        with patch("gateway.calendar_integration.is_available", return_value=False):
            events = life_awareness.today_events()
        assert isinstance(events, list)
        assert events == []

    def test_existing_dnd_caches_result(self):
        """Cache behavior remains compatible after calendar_source addition."""
        with patch("gateway.calendar_integration.is_available", return_value=True), \
             patch.object(life_awareness, "today_events", return_value=[]) as mock:
            life_awareness.do_not_disturb_status()
            life_awareness.do_not_disturb_status()
        mock.assert_called_once()
