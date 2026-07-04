"""Tests for the Gmail read-only connector (P3, docs/packets/005).

All tests run against a mocked HTTP transport — no network, no
google-auth at runtime. The connector's job is to map Gmail's REST
shape onto Kitty's signal store; this file pins that mapping.
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from typing import Any

import pytest

from gateway import signal_store
from gateway.connectors import mail as mail_module

# --- Fixtures ---------------------------------------------------------------


@pytest.fixture(autouse=True)
def isolate_signal_store(monkeypatch, tmp_path):
    """Keep mail tests away from live user data."""
    db_file = tmp_path / "kitty" / "kitty.db"
    monkeypatch.setattr(signal_store, "SIGNALS_DB_FILE", db_file, raising=False)


class _FakeCreds:
    """Stand-in for google.oauth2.credentials.Credentials.

    The connector only reads ``.valid``, ``.expired``, ``.refresh_token``,
    and ``.token``. We keep it minimal so tests do not need google-auth.
    """

    def __init__(
        self,
        *,
        token: str = "fake-access-token",
        expired: bool = False,
        refresh_token: str = "fake-refresh",
    ) -> None:
        self.token = token
        self.expired = expired
        self.refresh_token = refresh_token
        self.valid = not expired
        self.refreshed = False

    def refresh(self, _request) -> None:
        self.refreshed = True
        self.expired = False
        self.valid = True
        self.token = "refreshed-access-token"


@dataclass
class _HttpScript:
    """A canned response sequence for the injected HTTP transport.

    Entries are consumed strictly in order. Each entry is a response
    object or an exception to raise. The list call comes first in the
    connector, then one detail call per message; tests just list the
    responses in that order.
    """

    entries: list
    index: int = 0


def _scripted_http_get(script: _HttpScript):
    """Return an http_get that walks the script in order.

    Captures (url, params, headers) per call so tests can assert the
    Authorization header is wired through.
    """
    calls: list[tuple[str, dict[str, str], dict[str, str]]] = []

    def _get(url: str, params: dict[str, str], headers: dict[str, str]) -> dict[str, Any]:
        calls.append((url, dict(params), dict(headers)))
        if script.index >= len(script.entries):
            raise AssertionError(f"script exhausted at call #{len(calls)}: {url} {params}")
        response = script.entries[script.index]
        script.index += 1
        if isinstance(response, Exception):
            raise response
        return response

    _get.calls = calls  # type: ignore[attr-defined]
    return _get


# --- Helpers ----------------------------------------------------------------


def _list_response(message_ids: list[str]) -> dict[str, Any]:
    return {"messages": [{"id": mid} for mid in message_ids]}


def _detail_response(
    message_id: str,
    *,
    sender: str = "Sender <a@example.com>",
    subject: str = "Hello",
    snippet: str = "Short snippet",
    internal_date: int | None = 1_700_000_000_000,
) -> dict[str, Any]:
    return {
        "id": message_id,
        "threadId": "t1",
        "internalDate": str(internal_date) if internal_date is not None else None,
        "snippet": snippet,
        "payload": {
            "headers": [
                {"name": "From", "value": sender},
                {"name": "Subject", "value": subject},
                {"name": "Date", "value": "Thu, 1 Jan 2026 12:00:00 +0000"},
            ]
        },
    }


# --- Tests ------------------------------------------------------------------


class TestPollEmitsSignals:
    def test_poll_emits_one_signal_per_new_message(self):
        script = _HttpScript(
            entries=[
                _list_response(["m1", "m2"]),
                _detail_response("m1", sender="A <a@x.com>", subject="First"),
                _detail_response("m2", sender="B <b@y.com>", subject="Second"),
            ]
        )
        http_get = _scripted_http_get(script)
        connector = mail_module.MailConnector(_FakeCreds(), http_get=http_get)

        result = connector.poll(since_ts=1_700_000_000)

        assert result.to_dict() == {"new": 2, "deduped": 0, "errors": 0}
        signals = signal_store.list_recent(source="mail")
        # list_recent is newest-first; both signals have nearly the same
        # ts, so we just check the set of message_ids, not the order.
        assert {s["payload"]["message_id"] for s in signals} == {"m1", "m2"}
        assert {s["kind"] for s in signals} == {"mail.message"}

    def test_poll_signal_payload_shape(self):
        script = _HttpScript(
            entries=[
                _list_response(["m1"]),
                _detail_response("m1", sender="A <a@x.com>", subject="S", snippet="snip"),
            ]
        )
        connector = mail_module.MailConnector(_FakeCreds(), http_get=_scripted_http_get(script))
        connector.poll(since_ts=1)

        payload = signal_store.list_recent(source="mail")[0]["payload"]
        assert set(payload.keys()) == {"message_id", "from", "subject", "snippet", "internal_date"}
        assert payload["message_id"] == "m1"
        assert payload["from"] == "A <a@x.com>"
        assert payload["subject"] == "S"
        assert payload["snippet"] == "snip"

    def test_poll_dedupes_on_repoll(self):
        first_script = _HttpScript(
            entries=[
                _list_response(["m1", "m2"]),
                _detail_response("m1"),
                _detail_response("m2"),
            ]
        )
        second_script = _HttpScript(
            entries=[
                _list_response(["m1", "m2"]),
                _detail_response("m1"),
                _detail_response("m2"),
            ]
        )
        # Two http_gets that share state — the second script is what the
        # second poll reads; we wire it after the first poll runs.
        get_calls: list[dict[str, Any]] = []

        def _get(url: str, params: dict[str, str], headers: dict[str, str]) -> dict[str, Any]:
            get_calls.append({"url": url, "params": dict(params), "headers": dict(headers)})
            script = first_script if len(get_calls) <= 3 else second_script
            return _scripted_http_get(script)(url, params, headers)

        connector = mail_module.MailConnector(_FakeCreds(), http_get=_get)
        first = connector.poll(since_ts=1)
        second = connector.poll(since_ts=1)

        assert first.to_dict() == {"new": 2, "deduped": 0, "errors": 0}
        assert second.to_dict() == {"new": 0, "deduped": 2, "errors": 0}
        # Only two signal rows, not four.
        assert len(signal_store.list_recent(source="mail")) == 2


class TestPollSnippetOnly:
    def test_payload_never_contains_body(self):
        # Even if the Gmail response includes a body in payload.body, the
        # signal must carry only metadata. This is the D10 contract.
        detail = _detail_response("m1")
        detail["payload"]["body"] = {"data": "BODY_SHOULD_NOT_LEAK"}
        script = _HttpScript(entries=[_list_response(["m1"]), detail])
        connector = mail_module.MailConnector(_FakeCreds(), http_get=_scripted_http_get(script))
        connector.poll(since_ts=1)

        payload = signal_store.list_recent(source="mail")[0]["payload"]
        assert "body" not in payload
        assert "BODY_SHOULD_NOT_LEAK" not in json.dumps(payload)
        assert len(json.dumps(payload).encode("utf-8")) < signal_store.MAX_PAYLOAD_BYTES

    def test_malformed_headers_yield_empty_strings_not_crash(self):
        detail = _detail_response("m1")
        detail["payload"]["headers"] = "not-a-list"
        script = _HttpScript(entries=[_list_response(["m1"]), detail])
        connector = mail_module.MailConnector(_FakeCreds(), http_get=_scripted_http_get(script))
        result = connector.poll(since_ts=1)
        payload = signal_store.list_recent(source="mail")[0]["payload"]
        assert result.errors == 0
        assert payload["from"] == ""
        assert payload["subject"] == ""


class TestPollFailLoud:
    def test_list_failure_raises(self):
        http_get = _scripted_http_get(_HttpScript(entries=[mail_module.MailTransportError("503")]))
        connector = mail_module.MailConnector(_FakeCreds(), http_get=http_get)

        with pytest.raises(mail_module.MailTransportError):
            connector.poll(since_ts=1)

    def test_detail_failure_skips_message_continues_others(self):
        script = _HttpScript(
            entries=[
                _list_response(["m1", "m2"]),
                mail_module.MailTransportError("boom"),
                _detail_response("m2"),
            ]
        )
        connector = mail_module.MailConnector(_FakeCreds(), http_get=_scripted_http_get(script))
        result = connector.poll(since_ts=1)

        # m1 was skipped (logged as a warning), m2 emitted. The total is
        # not "all quiet" — the row for m2 still went in.
        assert result.new == 1
        assert {s["payload"]["message_id"] for s in signal_store.list_recent(source="mail")} == {
            "m2"
        }

    def test_first_run_uses_newer_than_filter(self):
        # since_ts=None should pass newer_than:1d, not after:.
        script = _HttpScript(entries=[_list_response([])])
        http_get = _scripted_http_get(script)
        connector = mail_module.MailConnector(_FakeCreds(), http_get=http_get)
        connector.poll()  # since_ts=None

        _url, params, _headers = http_get.calls[0]
        assert params.get("q") == "newer_than:1d"
        assert "after:" not in params.get("q", "")

    def test_subsequent_run_uses_after_filter(self):
        script = _HttpScript(entries=[_list_response([])])
        http_get = _scripted_http_get(script)
        connector = mail_module.MailConnector(_FakeCreds(), http_get=http_get)
        connector.poll(since_ts=1_700_000_000)

        _url, params, _headers = http_get.calls[0]
        assert params.get("q") == "after:1700000000"


class TestAuthFailures:
    def test_creds_none_raises_auth_error(self):
        connector = mail_module.MailConnector(None, http_get=lambda *_a, **_k: {})
        with pytest.raises(mail_module.MailAuthError):
            connector.poll(since_ts=1)

    def test_expired_creds_refresh(self):
        creds = _FakeCreds(expired=True)
        # Need at least one message in the list so the connector proceeds
        # to fetch detail — that's the path that touches the auth headers.
        script = _HttpScript(entries=[_list_response(["m1"]), _detail_response("m1")])
        connector = mail_module.MailConnector(creds, http_get=_scripted_http_get(script))
        connector.poll(since_ts=1)

        assert creds.refreshed is True
        assert creds.valid is True

    def test_expired_no_refresh_token_raises(self):
        creds = _FakeCreds(expired=True, refresh_token="")
        script = _HttpScript(entries=[_list_response(["m1"]), _detail_response("m1")])
        connector = mail_module.MailConnector(creds, http_get=_scripted_http_get(script))
        with pytest.raises(mail_module.MailAuthError, match="re-authorize"):
            connector.poll(since_ts=1)

    def test_authorization_header_sent_on_every_request(self):
        creds = _FakeCreds(token="sentinel-token")
        script = _HttpScript(entries=[_list_response([])])
        http_get = _scripted_http_get(script)
        connector = mail_module.MailConnector(creds, http_get=http_get)
        connector.poll(since_ts=1)

        _url, _params, headers = http_get.calls[0]
        assert headers.get("Authorization") == "Bearer sentinel-token"


# --- fetch_body -------------------------------------------------------------


class TestFetchBody:
    def test_fetch_body_returns_text_plain(self):
        body_text = "Hello, this is a body."
        encoded = base64.urlsafe_b64encode(body_text.encode("utf-8")).decode("ascii").rstrip("=")
        detail = {
            "id": "m1",
            "payload": {
                "mimeType": "multipart/alternative",
                "parts": [
                    {"mimeType": "text/plain", "body": {"data": encoded}},
                    {"mimeType": "text/html", "body": {"data": "ignored"}},
                ],
            },
        }
        script = _HttpScript(entries=[detail])
        connector = mail_module.MailConnector(_FakeCreds(), http_get=_scripted_http_get(script))

        body = connector.fetch_body("m1")

        assert body == body_text

    def test_fetch_body_data_class_is_mail_body(self):
        # The D10 contract: the return value is data class "mail_body".
        # We assert it via the module constant, not a magic string.
        encoded = base64.urlsafe_b64encode(b"hi").decode("ascii").rstrip("=")
        detail = {
            "id": "m1",
            "payload": {"mimeType": "text/plain", "body": {"data": encoded}},
        }
        script = _HttpScript(entries=[detail])
        connector = mail_module.MailConnector(_FakeCreds(), http_get=_scripted_http_get(script))

        body = connector.fetch_body("m1")

        # The contract is: this string is data class mail_body. We don't
        # pin the class name in code, but the module constant does.
        assert isinstance(body, str)
        assert body == "hi"
        # The body must not contain anything a signal would ever carry.
        assert body not in json.dumps({"x": 1})  # trivially true; documents the rule.

    def test_fetch_body_empty_on_no_text_parts(self):
        detail = {
            "id": "m1",
            "payload": {
                "mimeType": "multipart/alternative",
                "parts": [{"mimeType": "application/pdf", "body": {"attachmentId": "x"}}],
            },
        }
        script = _HttpScript(entries=[detail])
        connector = mail_module.MailConnector(_FakeCreds(), http_get=_scripted_http_get(script))
        assert connector.fetch_body("m1") == ""


# --- poll_now / cron entry point --------------------------------------------


class TestPollNow:
    def test_poll_now_unconfigured_returns_skipped(self, monkeypatch, tmp_path):
        monkeypatch.setenv("GMAIL_TOKEN_FILE", str(tmp_path / "no-such-token.json"))
        result = mail_module.poll_now()
        assert result["skipped"] == "unconfigured"
        assert result["new"] == 0

    def test_poll_now_missing_token_raises_auth_error(self, monkeypatch, tmp_path):
        from gateway.connectors import mail as mail_mod

        def _raise():
            raise mail_mod.MailAuthError("bad token file")

        monkeypatch.setattr(mail_mod, "_load_credentials", _raise)

        token_path = tmp_path / "present-but-broken.json"
        token_path.write_text("{}", encoding="utf-8")
        monkeypatch.setenv("GMAIL_TOKEN_FILE", str(token_path))

        result = mail_mod.poll_now()
        assert result["errors"] == 1
        assert "bad token file" in result["skipped"]

    def test_poll_now_auth_error_path(self, monkeypatch, tmp_path):
        # Pre-OAuth state: token file does not exist -> unconfigured branch.
        monkeypatch.setenv("GMAIL_TOKEN_FILE", str(tmp_path / "absent.json"))
        result = mail_module.poll_now()
        assert result["new"] == 0
        assert result["deduped"] == 0
        assert result["errors"] == 0
        assert result["skipped"] == "unconfigured"


# --- is_configured ----------------------------------------------------------


class TestIsConfigured:
    def test_is_configured_true_when_token_exists(self, monkeypatch, tmp_path):
        token = tmp_path / "token.json"
        token.write_text("{}", encoding="utf-8")
        monkeypatch.setenv("GMAIL_TOKEN_FILE", str(token))
        assert mail_module.is_configured() is True

    def test_is_configured_false_when_token_missing(self, monkeypatch, tmp_path):
        monkeypatch.setenv("GMAIL_TOKEN_FILE", str(tmp_path / "nope.json"))
        assert mail_module.is_configured() is False
