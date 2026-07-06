"""Tests for the push façade (P3, docs/packets/015)."""
from __future__ import annotations

from datetime import datetime
from unittest.mock import patch

from gateway import push


def _clear_log(monkeypatch, tmp_path):
    monkeypatch.setattr(push, "PUSH_LOG_FILE", tmp_path / "push_log.jsonl")


class TestChannels:
    def test_default_channel_order(self, monkeypatch):
        monkeypatch.delenv("PUSH_CHANNELS", raising=False)
        assert push._channels() == ["imessage", "pushover"]

    def test_custom_channel_order(self, monkeypatch):
        monkeypatch.setenv("PUSH_CHANNELS", "pushover, imessage")
        assert push._channels() == ["pushover", "imessage"]


class TestQuietHours:
    def test_absent_quiet_hours_returns_none(self, monkeypatch, tmp_path):
        monkeypatch.setattr(push, "USER_PROFILE_PATH", tmp_path / "missing.json")
        assert push._quiet_hours_window() is None

    def test_reads_quiet_hours_from_profile(self, monkeypatch, tmp_path):
        profile = tmp_path / "user_profile.json"
        profile.write_text('{"quiet_hours": "23:00-08:00"}', encoding="utf-8")
        monkeypatch.setattr(push, "USER_PROFILE_PATH", profile)
        assert push._quiet_hours_window() == "23:00-08:00"

    def test_in_quiet_hours_wraps_midnight(self):
        window = "23:00-08:00"
        assert push._in_quiet_hours(window, datetime(2026, 1, 1, 23, 30)) is True
        assert push._in_quiet_hours(window, datetime(2026, 1, 1, 6, 0)) is True
        assert push._in_quiet_hours(window, datetime(2026, 1, 1, 12, 0)) is False

    def test_in_quiet_hours_same_day_window(self):
        window = "13:00-14:00"
        assert push._in_quiet_hours(window, datetime(2026, 1, 1, 13, 30)) is True
        assert push._in_quiet_hours(window, datetime(2026, 1, 1, 15, 0)) is False

    def test_malformed_window_does_not_raise(self):
        assert push._in_quiet_hours("garbage", datetime(2026, 1, 1, 12, 0)) is False


class TestPushToJacob:
    def test_tries_channels_in_order_first_success_wins(self, monkeypatch, tmp_path):
        _clear_log(monkeypatch, tmp_path)
        monkeypatch.setenv("PUSH_CHANNELS", "imessage,pushover")
        with patch.dict(push._SENDERS, {"imessage": lambda *_: False, "pushover": lambda *_: True}):
            assert push.push_to_jacob("hi") is True

    def test_falls_back_when_first_channel_fails(self, monkeypatch, tmp_path):
        _clear_log(monkeypatch, tmp_path)
        monkeypatch.setenv("PUSH_CHANNELS", "imessage,pushover")
        calls = []

        def fail(*_a):
            calls.append("imessage")
            return False

        def succeed(*_a):
            calls.append("pushover")
            return True

        with patch.dict(push._SENDERS, {"imessage": fail, "pushover": succeed}):
            assert push.push_to_jacob("hi") is True
        assert calls == ["imessage", "pushover"]

    def test_all_channels_down_returns_false(self, monkeypatch, tmp_path):
        _clear_log(monkeypatch, tmp_path)
        monkeypatch.setenv("PUSH_CHANNELS", "imessage,pushover")
        with patch.dict(push._SENDERS, {"imessage": lambda *_: False, "pushover": lambda *_: False}):
            assert push.push_to_jacob("hi") is False

    def test_channel_raising_is_treated_as_failure_not_propagated(self, monkeypatch, tmp_path):
        _clear_log(monkeypatch, tmp_path)
        monkeypatch.setenv("PUSH_CHANNELS", "imessage,pushover")

        def boom(*_a):
            raise RuntimeError("transport exploded")

        with patch.dict(push._SENDERS, {"imessage": boom, "pushover": lambda *_: True}):
            assert push.push_to_jacob("hi") is True

    def test_every_attempt_logged(self, monkeypatch, tmp_path):
        _clear_log(monkeypatch, tmp_path)
        monkeypatch.setenv("PUSH_CHANNELS", "imessage,pushover")
        with patch.dict(push._SENDERS, {"imessage": lambda *_: False, "pushover": lambda *_: True}):
            push.push_to_jacob("hi", kind="info", title="Kitty")
        entries = push._recent_log_entries()
        assert len(entries) == 2
        assert entries[0]["channel"] == "imessage"
        assert entries[0]["ok"] is False
        assert entries[1]["channel"] == "pushover"
        assert entries[1]["ok"] is True

    def test_unknown_channel_is_skipped(self, monkeypatch, tmp_path):
        _clear_log(monkeypatch, tmp_path)
        monkeypatch.setenv("PUSH_CHANNELS", "carrier-pigeon,pushover")
        with patch.dict(push._SENDERS, {"pushover": lambda *_: True}):
            assert push.push_to_jacob("hi") is True

    def test_quiet_hours_defers_info_and_does_not_touch_channels(self, monkeypatch, tmp_path):
        _clear_log(monkeypatch, tmp_path)
        profile = tmp_path / "user_profile.json"
        profile.write_text('{"quiet_hours": "00:00-23:59"}', encoding="utf-8")
        monkeypatch.setattr(push, "USER_PROFILE_PATH", profile)
        called = []
        with patch.dict(push._SENDERS, {"imessage": lambda *_: called.append(1) or True}):
            result = push.push_to_jacob("hi", kind="info")
        assert result is False
        assert called == []

    def test_quiet_hours_does_not_defer_alert(self, monkeypatch, tmp_path):
        _clear_log(monkeypatch, tmp_path)
        monkeypatch.setenv("PUSH_CHANNELS", "imessage")
        profile = tmp_path / "user_profile.json"
        profile.write_text('{"quiet_hours": "00:00-23:59"}', encoding="utf-8")
        monkeypatch.setattr(push, "USER_PROFILE_PATH", profile)
        with patch.dict(push._SENDERS, {"imessage": lambda *_: True}):
            assert push.push_to_jacob("wake up", kind="alert") is True

    def test_dedupe_suppresses_repeat_within_24h(self, monkeypatch, tmp_path):
        _clear_log(monkeypatch, tmp_path)
        monkeypatch.setenv("PUSH_CHANNELS", "imessage")
        calls = []
        with patch.dict(push._SENDERS, {"imessage": lambda *_: calls.append(1) or True}):
            assert push.push_to_jacob("hi", dedupe_key="daily-brief") is True
            assert push.push_to_jacob("hi", dedupe_key="daily-brief") is True
        assert calls == [1]

    def test_dedupe_does_not_suppress_after_a_failed_attempt(self, monkeypatch, tmp_path):
        _clear_log(monkeypatch, tmp_path)
        monkeypatch.setenv("PUSH_CHANNELS", "imessage")
        with patch.dict(push._SENDERS, {"imessage": lambda *_: False}):
            assert push.push_to_jacob("hi", dedupe_key="daily-brief") is False
        with patch.dict(push._SENDERS, {"imessage": lambda *_: True}):
            assert push.push_to_jacob("hi", dedupe_key="daily-brief") is True

    def test_url_passed_through_to_pushover_not_imessage(self, monkeypatch, tmp_path):
        _clear_log(monkeypatch, tmp_path)
        monkeypatch.setenv("PUSH_CHANNELS", "pushover")
        seen = {}

        def fake_pushover(message, title, url):
            seen["url"] = url
            return True

        with patch.dict(push._SENDERS, {"pushover": fake_pushover}):
            push.push_to_jacob("hi", url="https://kitty.local")
        assert seen["url"] == "https://kitty.local"


class TestSendImessage:
    def test_disabled_without_recipient(self, monkeypatch):
        monkeypatch.delenv("PUSH_IMESSAGE_RECIPIENT", raising=False)
        assert push._send_imessage("hi", "title", None) is False

    def test_calls_imessage_send_with_recipient(self, monkeypatch):
        monkeypatch.setenv("PUSH_IMESSAGE_RECIPIENT", "+15551234567")
        with patch("gateway.imessage.send", return_value=True) as mock_send:
            assert push._send_imessage("hi", "title", None) is True
        mock_send.assert_called_once_with("+15551234567", "hi")


class TestSendPushover:
    def test_disabled_when_not_configured(self, monkeypatch):
        with patch("gateway.notify.is_configured", return_value=False):
            assert push._send_pushover("hi", "title", None) is False

    def test_calls_notify_send_when_configured(self, monkeypatch):
        with patch("gateway.notify.is_configured", return_value=True):
            with patch("gateway.notify.send", return_value=True) as mock_send:
                assert push._send_pushover("hi", "title", "https://x") is True
        mock_send.assert_called_once_with("hi", title="title", url="https://x")
