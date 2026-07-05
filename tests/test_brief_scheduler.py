"""Tests for the daily brief scheduler."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import patch

import pytest


class TestBriefScheduler:
    def test_load_brief_time_defaults_to_0800(self, tmp_path, monkeypatch):
        from gateway import brief_scheduler

        monkeypatch.setattr(
            brief_scheduler, "USER_PROFILE_PATH", tmp_path / "missing.json"
        )
        assert brief_scheduler.load_brief_time() == "08:00"

    def test_load_brief_time_reads_profile(self, tmp_path, monkeypatch):
        from gateway import brief_scheduler

        profile = tmp_path / "user_profile.json"
        profile.write_text('{"brief_time": "07:30"}')
        monkeypatch.setattr(brief_scheduler, "USER_PROFILE_PATH", profile)
        assert brief_scheduler.load_brief_time() == "07:30"

    def test_seconds_until_tomorrow_when_time_passed(self):
        from gateway.brief_scheduler import seconds_until

        now = datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)
        assert seconds_until("08:00", now) == 20 * 3600

    def test_seconds_until_later_today(self):
        from gateway.brief_scheduler import seconds_until

        now = datetime(2026, 6, 1, 6, 0, tzinfo=timezone.utc)
        assert seconds_until("08:00", now) == 2 * 3600

    def test_generate_and_deliver_brief_contains_today_and_bullets(self, tmp_path, monkeypatch):
        from gateway import brief_scheduler

        today = datetime.now(timezone.utc).date().isoformat()
        fake_brief = {
            "date": today,
            "intention": "Focus on shipping",
            "headlines": [{"title": "AI progress continues"}],
            "inbox_items": [{"text": "Review PR #42"}],
            "signals": [{"payload": {"message": "New signal"}}],
        }

        with patch("gateway.brief.generate_brief", return_value=fake_brief):
            with patch("gateway.push.push_to_jacob", return_value=False):
                text = brief_scheduler.generate_and_deliver_brief()

        assert f"Brief for {today}" in text
        bullets = [line for line in text.splitlines() if line.startswith("- ")]
        assert len(bullets) >= 1
        assert any("Review PR #42" in line for line in bullets)

    def test_format_brief_text_includes_whats_b_bullets(self):
        from gateway import brief_scheduler

        today = datetime.now(timezone.utc).date().isoformat()
        fake_brief = {
            "date": today,
            "next_steps": [
                {"project_id": 1, "project_name": "kitty", "step": "write the migration", "why": "unblocks the rest"},
            ],
        }

        text = brief_scheduler._format_brief_text(fake_brief)

        assert "- kitty: write the migration" in text

    def test_generate_and_deliver_brief_reaches_push_facade_exactly_once(self, monkeypatch):
        from gateway import brief_scheduler

        fake_brief = {"date": "2026-07-04", "intention": "Ship the phone channel"}
        with patch("gateway.brief.generate_brief", return_value=fake_brief):
            with patch("gateway.push.push_to_jacob", return_value=True) as mock_push:
                text = brief_scheduler.generate_and_deliver_brief()

        mock_push.assert_called_once()
        args, kwargs = mock_push.call_args
        assert args[0] == text
        assert kwargs["kind"] == "info"
        assert kwargs["title"] == "Kitty Morning Brief"

    @pytest.mark.asyncio
    async def test_scheduler_triggers_and_generates_brief(self, tmp_path, monkeypatch):
        from gateway import brief_scheduler

        profile = tmp_path / "user_profile.json"
        profile.write_text('{"brief_time": "08:00"}')
        monkeypatch.setattr(brief_scheduler, "USER_PROFILE_PATH", profile)

        today = datetime.now(timezone.utc).date().isoformat()

        delivered: list[str] = []

        def fake_generate_and_deliver() -> str:
            text = f"Brief for {today}\n- Intention: Ship the scheduler"
            delivered.append(text)
            return text

        monkeypatch.setattr(
            brief_scheduler, "generate_and_deliver_brief", fake_generate_and_deliver
        )
        # Trigger immediately and then stop after one iteration.
        monkeypatch.setattr(brief_scheduler, "seconds_until", lambda _t, _n: 0)

        task = asyncio.create_task(brief_scheduler._scheduler_loop())
        # Give the loop one chance to fire and then cancel it.
        await asyncio.sleep(0.05)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        assert len(delivered) >= 1
        assert f"Brief for {today}" in delivered[0]
        assert "- Intention: Ship the scheduler" in delivered[0]
