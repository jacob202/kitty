"""Tests for notify — Pushover integration."""
import pytest
from unittest.mock import patch, MagicMock
from gateway.notify import send, send_brief, send_alert, is_configured, _get_keys


class TestGetKeys:
    def test_no_keys_returns_empty(self):
        with patch.dict("os.environ", {}, clear=True):
            user, token = _get_keys()
            assert user == ""
            assert token == ""

    def test_keys_set(self):
        with patch.dict("os.environ", {"PUSHOVER_USER_KEY": "u123", "PUSHOVER_API_TOKEN": "t456"}, clear=True):
            user, token = _get_keys()
            assert user == "u123"
            assert token == "t456"


class TestSend:
    def test_skips_when_not_configured(self):
        with patch.dict("os.environ", {}, clear=True):
            assert send("test") is False

    def test_sends_when_configured(self):
        with patch.dict("os.environ", {"PUSHOVER_USER_KEY": "u", "PUSHOVER_API_TOKEN": "t"}, clear=True), \
             patch("gateway.notify.requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            assert send("hello", title="Test") is True
            mock_post.assert_called_once()

    def test_handles_http_error(self):
        with patch.dict("os.environ", {"PUSHOVER_USER_KEY": "u", "PUSHOVER_API_TOKEN": "t"}, clear=True), \
             patch("gateway.notify.requests.post") as mock_post:
            mock_post.return_value.status_code = 400
            mock_post.return_value.text = "bad request"
            assert send("hello") is False

    def test_handles_network_error(self):
        with patch.dict("os.environ", {"PUSHOVER_USER_KEY": "u", "PUSHOVER_API_TOKEN": "t"}, clear=True), \
             patch("gateway.notify.requests.post", side_effect=Exception("timeout")):
            assert send("hello") is False


class TestSendBrief:
    def test_send_brief_delegates(self):
        with patch.dict("os.environ", {"PUSHOVER_USER_KEY": "u", "PUSHOVER_API_TOKEN": "t"}, clear=True), \
             patch("gateway.notify.requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            assert send_brief("morning summary") is True


class TestIsConfigured:
    def test_false_without_keys(self):
        with patch.dict("os.environ", {}, clear=True):
            assert is_configured() is False

    def test_true_with_keys(self):
        with patch.dict("os.environ", {"PUSHOVER_USER_KEY": "u", "PUSHOVER_API_TOKEN": "t"}, clear=True):
            assert is_configured() is True
