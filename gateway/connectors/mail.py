"""Gmail read-only connector (P3, docs/packets/005).

Polls Gmail for new messages and emits deduped signal rows. Fetches
full bodies only on explicit demand; bodies are data class ``mail_body``
under D10 (local-only — never put one in a signal payload).

Scope: ``https://www.googleapis.com/auth/gmail.readonly``. No send,
no modify, no labels — Google rejects anything else before the code
sees it, and this module refuses to construct any other request.

The transport layer is injectable so tests can drive the connector
without ever touching the network. The default transport uses
``google-auth`` for the token dance and ``requests`` for the two
Gmail REST calls (``users.messages.list`` and ``users.messages.get``).
``google-api-python-client`` is intentionally not used — discovery +
httplib2 for two endpoints is not worth the dep.

Public API:
  MailConnector(creds, *, http_get=None, http_post=None)
      Wrap a ``google.oauth2.credentials.Credentials`` and (optionally)
      injected HTTP callables. ``creds`` is opaque to tests — the only
      requirement is that ``creds.valid`` is a bool and ``creds.expired``
      triggers a refresh via the injected (or default) request.
  connector.poll(since_ts=None) -> dict
      List messages newer than ``since_ts`` and emit signals.
      Returns ``{"new": int, "deduped": int, "errors": 0}``.
      ``since_ts`` is a Unix epoch in seconds. First-run callers pass
      ``None`` and the connector uses Gmail's ``newer_than:1d`` filter
      as a safe default.
  connector.fetch_body(message_id) -> str
      Fetch a full message body. The returned string is data class
      ``mail_body`` (D10) — the caller must not put it in a signal
      payload. text/plain preferred; base64url decoded.

Errors: ``MailConnectorError`` (base), ``MailAuthError`` (credentials
unusable), ``MailTransportError`` (non-200 from Gmail). All raise —
never return an empty list to mask a broken connector.

Cron entry point: ``poll_now()`` — loads creds from disk (or returns
a warning) and runs ``poll()``. Wired into ``gateway.app`` as
``mail.poll``. A missing token file logs once per run and returns;
a broken token raises (the cron runner logs the failure but does
not crash).
"""

from __future__ import annotations

import base64
import json
import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

from gateway.paths import DATA_DIR

logger = logging.getLogger("kitty.connector.mail")

# Public, read-only — Google rejects anything else before our code sees it.
GMAIL_READONLY_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"

# Default Gmail API base. Tests inject http_get/http_post and never touch this.
GMAIL_API_BASE = "https://gmail.googleapis.com/gmail/v1/users/me"

# Where the OAuth client secret lives (Jacob sets GMAIL_CLIENT_SECRET_FILE in .env).
# Where the granted token lands.
DEFAULT_TOKEN_PATH = DATA_DIR / "gmail_token.json"

# Data class tag for bodies, per D10 (privacy boundary in router).
# Lint/docs only — enforced where bodies meet LLM calls, not here.
BODY_DATA_CLASS = "mail_body"


class MailConnectorError(RuntimeError):
    """Base for mail-connector failures. Subclasses narrow the cause."""


class MailAuthError(MailConnectorError):
    """Credentials missing, malformed, or beyond refresh."""


class MailTransportError(MailConnectorError):
    """Gmail returned non-200, or the network call failed in an unexpected way."""


@dataclass
class PollResult:
    """Counts from one ``poll()`` run. Signals are written as a side effect."""

    new: int
    deduped: int
    errors: int = 0

    def to_dict(self) -> dict[str, int]:
        return {"new": self.new, "deduped": self.deduped, "errors": self.errors}


# Type aliases for injected HTTP callables. Both return a parsed JSON body
# on a 2xx, or raise MailTransportError on anything else. The auth headers
# are computed once per call and passed in by the connector — tests can
# capture or ignore them as needed.
HttpGet = Callable[[str, dict[str, str], dict[str, str]], dict[str, Any]]
HttpPost = Callable[[str, dict[str, str], dict[str, Any]], dict[str, Any]]


def _default_http_get(url: str, params: dict[str, str], headers: dict[str, str]) -> dict[str, Any]:
    """Default GET using the requests library. Imports lazily for test speed."""
    import requests

    resp = requests.get(url, params=params, headers=headers, timeout=15)
    if not 200 <= resp.status_code < 300:
        raise MailTransportError(f"Gmail GET failed: {resp.status_code} {resp.text[:200]}")
    return resp.json()


def _default_http_post(url: str, headers: dict[str, str], body: dict[str, Any]) -> dict[str, Any]:
    """Default POST using the requests library. Imports lazily for test speed."""
    import requests

    resp = requests.post(url, headers=headers, json=body, timeout=15)
    if not 200 <= resp.status_code < 300:
        raise MailTransportError(f"Gmail POST failed: {resp.status_code} {resp.text[:200]}")
    return resp.json()


class MailConnector:
    """Read-only Gmail connector. See module docstring for the contract."""

    SOURCE = "mail"
    KIND = "mail.message"

    def __init__(
        self,
        creds: Any,
        *,
        http_get: Optional[HttpGet] = None,
        http_post: Optional[HttpPost] = None,
        api_base: str = GMAIL_API_BASE,
    ) -> None:
        self._creds = creds
        self._http_get = http_get or _default_http_get
        self._http_post = http_post or _default_http_post
        self._api_base = api_base

    def _auth_headers(self) -> dict[str, str]:
        if self._creds is None:
            raise MailAuthError("no credentials bound to connector")
        if not getattr(self._creds, "valid", False):
            self._refresh_if_possible()
        token = getattr(self._creds, "token", None)
        if not token:
            raise MailAuthError("credentials have no access token and refresh failed")
        return {"Authorization": f"Bearer {token}"}

    def _refresh_if_possible(self) -> None:
        """Refresh the creds if expired. Raises MailAuthError on a hard failure."""
        if not getattr(self._creds, "expired", False):
            return
        if not getattr(self._creds, "refresh_token", None):
            raise MailAuthError("credentials expired and have no refresh token — re-authorize")
        try:
            from google.auth.transport.requests import Request

            self._creds.refresh(Request())
        except Exception as exc:
            raise MailAuthError(f"token refresh failed: {exc}") from exc
        if not getattr(self._creds, "valid", False):
            raise MailAuthError("token refresh did not produce a valid credential")

    def poll(self, since_ts: Optional[float] = None) -> PollResult:
        """List messages newer than ``since_ts`` and emit deduped signals.

        ``since_ts=None`` is the first-run case: fall back to
        ``newer_than:1d`` so a fresh connector does not try to backfill
        a year of mail.
        """
        # Fail loud up front on missing creds — easier to debug than
        # watching the list call fail with a generic auth error.
        if self._creds is None:
            raise MailAuthError("no credentials bound to connector")

        # Import lazily so the module imports cheaply for callers that
        # only use the doctor check or the auth helper.
        from gateway.signal_store import MAX_PAYLOAD_BYTES, emit

        params: dict[str, str] = {"maxResults": "50"}
        if since_ts is None:
            params["q"] = "newer_than:1d"
        else:
            # Gmail q=after:UNIX_SECS — its parser wants an int, no decimal.
            params["q"] = f"after:{int(since_ts)}"

        try:
            list_resp = self._http_get(f"{self._api_base}/messages", params, self._auth_headers())
        except MailTransportError:
            raise
        except MailConnectorError:
            raise
        except Exception as exc:
            raise MailTransportError(f"Gmail list failed: {exc}") from exc

        messages = list_resp.get("messages", []) or []
        new_count = 0
        deduped_count = 0
        for entry in messages:
            message_id = entry.get("id")
            if not message_id:
                continue
            try:
                detail = self._fetch_metadata(message_id)
            except MailConnectorError as exc:
                logger.warning("mail: failed to fetch %s: %s", message_id, exc)
                continue
            payload = self._signal_payload(message_id, detail)
            # Defensive: the metadata path must never exceed the row cap.
            # fetch_body never lands here.
            if len(json.dumps(payload).encode("utf-8")) > MAX_PAYLOAD_BYTES:
                raise MailTransportError(
                    f"mail signal payload for {message_id} exceeds "
                    f"{MAX_PAYLOAD_BYTES} bytes — refusing to emit"
                )
            record = emit(
                source=self.SOURCE,
                kind=self.KIND,
                payload=payload,
                dedupe_key=f"mail:{message_id}",
            )
            if record is None:
                deduped_count += 1
            else:
                new_count += 1

        return PollResult(new=new_count, deduped=deduped_count)

    def _fetch_metadata(self, message_id: str) -> dict[str, Any]:
        """GET the message in format=metadata with just the fields we use."""
        params = {
            "format": "metadata",
            "metadataHeaders": "From,Subject",
        }
        return self._http_get(
            f"{self._api_base}/messages/{message_id}",
            params,
            self._auth_headers(),
        )

    @staticmethod
    def _signal_payload(message_id: str, detail: dict[str, Any]) -> dict[str, Any]:
        """Build the deduped signal payload from a Gmail message detail.

        Snippet only — never the body. Header parsing is best-effort; a
        malformed header string yields an empty value rather than a crash,
        so a single weird message cannot break the whole poll.
        """
        headers = {
            h.get("name", "").lower(): h.get("value", "")
            for h in (detail.get("payload", {}) or {}).get("headers", [])
            if isinstance(h, dict)
        }
        return {
            "message_id": message_id,
            "from": headers.get("from", "").strip(),
            "subject": headers.get("subject", "").strip(),
            "snippet": (detail.get("snippet") or "").strip(),
            "internal_date": detail.get("internalDate"),
        }

    def fetch_body(self, message_id: str) -> str:
        """Fetch a full message body, text/plain preferred.

        The returned string is data class ``mail_body`` (D10) — local-only
        under the privacy boundary. The caller must not put the return
        value into a signal payload; ``signal_store.MAX_PAYLOAD_BYTES``
        would block it, but the rule is "don't try" not "let the store
        catch it."
        """
        params = {"format": "full"}
        detail = self._http_get(
            f"{self._api_base}/messages/{message_id}",
            params,
            self._auth_headers(),
        )
        return _decode_body(detail)


def _decode_body(detail: dict[str, Any]) -> str:
    """Walk the message parts, prefer text/plain, decode base64url.

    Multipart messages: first text/plain found, else first text/* with
    data, else empty string. Empty string is still a valid result —
    the caller decides what to do with it.
    """
    payload = detail.get("payload") or {}
    parts = payload.get("parts") or []
    candidates: list[tuple[int, str]] = []  # (priority, decoded_text)
    if parts:
        for part in parts:
            mime = (part.get("mimeType") or "").lower()
            data = part.get("body", {}).get("data")
            if not data or not mime.startswith("text/"):
                continue
            decoded = _b64url_decode(data)
            priority = 0 if mime == "text/plain" else 1
            candidates.append((priority, decoded))
    else:
        data = payload.get("body", {}).get("data")
        if data:
            candidates.append((0, _b64url_decode(data)))
    if not candidates:
        return ""
    candidates.sort(key=lambda t: t[0])
    return candidates[0][1]


def _b64url_decode(data: str) -> str:
    """Gmail uses URL-safe base64 without padding. Return text or '' on garbage."""
    if not data:
        return ""
    padded = data + "=" * (-len(data) % 4)
    try:
        raw = base64.urlsafe_b64decode(padded.encode("ascii"))
    except (ValueError, TypeError):
        return ""
    try:
        return raw.decode("utf-8", errors="replace")
    except Exception:
        return raw.decode("latin-1", errors="replace")


# --- Cron entry point -------------------------------------------------------


def _load_credentials() -> Any:
    """Load Gmail OAuth credentials from the token file. Raises MailAuthError."""
    from google.oauth2.credentials import Credentials

    token_path = Path(os.environ.get("GMAIL_TOKEN_FILE", str(DEFAULT_TOKEN_PATH)))
    if not token_path.exists():
        raise MailAuthError(f"gmail token file not found: {token_path}")
    try:
        creds = Credentials.from_authorized_user_file(str(token_path), GMAIL_READONLY_SCOPE)
    except (OSError, ValueError) as exc:
        raise MailAuthError(f"cannot read gmail token file: {exc}") from exc
    return creds


def is_configured() -> bool:
    """True if the token file is on disk and the env var (if set) points to a real file.

    The OAuth client secret path is only required for the one-time consent
    flow (`--auth`); the polling path only needs the token file. So this
    check is "do we have a usable token" — not "is the env fully populated."
    """
    token_path = Path(os.environ.get("GMAIL_TOKEN_FILE", str(DEFAULT_TOKEN_PATH)))
    return token_path.exists()


def poll_now() -> dict[str, Any]:
    """Cron entry point: load creds, poll, return a result dict.

    Missing token file -> warn and return an empty result (so a not-yet-
    configured connector does not crash the cron runner). Anything else
    raises — the cron runner logs it and moves on.
    """
    if not is_configured():
        logger.warning("mail.poll skipped: gmail token file not present")
        return {"new": 0, "deduped": 0, "errors": 0, "skipped": "unconfigured"}
    try:
        creds = _load_credentials()
    except MailAuthError as exc:
        logger.warning("mail.poll auth error: %s", exc)
        return {"new": 0, "deduped": 0, "errors": 1, "skipped": str(exc)}
    connector = MailConnector(creds)
    try:
        result = connector.poll()
    except MailConnectorError as exc:
        logger.warning("mail.poll failed: %s", exc)
        return {"new": 0, "deduped": 0, "errors": 1, "skipped": str(exc)}
    return result.to_dict()


# --- Auth helper (one-time consent) ----------------------------------------


def run_auth() -> int:
    """One-time OAuth consent flow. Run as ``python -m gateway.connectors.mail --auth``.

    Reads the OAuth client secret from ``GMAIL_CLIENT_SECRET_FILE``, opens
    a local server for the redirect, and writes the granted token to
    ``DEFAULT_TOKEN_PATH`` (or ``GMAIL_TOKEN_FILE`` if set).
    """
    import argparse

    parser = argparse.ArgumentParser(prog="gateway.connectors.mail")
    parser.add_argument(
        "--auth",
        action="store_true",
        help="Run the one-time OAuth consent flow and write the token to disk.",
    )
    args = parser.parse_args()
    if not args.auth:
        parser.print_help()
        return 0

    secret_path = os.environ.get("GMAIL_CLIENT_SECRET_FILE", "").strip()
    if not secret_path:
        print("GMAIL_CLIENT_SECRET_FILE is not set — see .env.example", file=sys.stderr)
        return 2
    if not Path(secret_path).exists():
        print(f"client secret file not found: {secret_path}", file=sys.stderr)
        return 2

    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError as exc:
        print(f"google-auth-oauthlib is not installed: {exc}", file=sys.stderr)
        return 2

    flow = InstalledAppFlow.from_client_secrets_file(secret_path, [GMAIL_READONLY_SCOPE])
    creds = flow.run_local_server(port=0)
    token_path = Path(os.environ.get("GMAIL_TOKEN_FILE", str(DEFAULT_TOKEN_PATH)))
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(creds.to_json(), encoding="utf-8")
    print(f"token written to {token_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run_auth())
