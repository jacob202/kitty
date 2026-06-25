"""Tests for mcp.imagen.retry — tenacity decorator retries transient failures."""

from __future__ import annotations

import httpx
import pytest

from mcp.imagen.retry import retry_with_backoff


def test_retry_succeeds_on_first_attempt() -> None:
    """No retry needed when the call succeeds immediately."""
    calls = 0

    @retry_with_backoff(attempts=3)
    def fn() -> str:
        nonlocal calls
        calls += 1
        return "ok"

    assert fn() == "ok"
    assert calls == 1


def test_retry_succeeds_after_transient_failure() -> None:
    """A transient error followed by success retries and returns the result."""
    calls = 0

    @retry_with_backoff(attempts=3)
    def fn() -> str:
        nonlocal calls
        calls += 1
        if calls < 2:
            raise httpx.HTTPStatusError(
                "429 rate limited",
                request=httpx.Request("POST", "https://example.test"),
                response=httpx.Response(429),
            )
        return "recovered"

    # The exponential backoff min is 1s, so this takes ~1s.
    result = fn()
    assert result == "recovered"
    assert calls == 2


def test_retry_exhausts_and_reraises() -> None:
    """After max attempts, the real exception is reraised (fail loud)."""
    calls = 0

    @retry_with_backoff(attempts=3)
    def fn() -> str:
        nonlocal calls
        calls += 1
        raise httpx.ConnectError("connection refused")

    with pytest.raises(httpx.ConnectError):
        fn()
    assert calls == 3


def test_retry_does_not_retry_non_retryable() -> None:
    """ValueError is not in the retryable set — no retry."""
    calls = 0

    @retry_with_backoff(attempts=3)
    def fn() -> str:
        nonlocal calls
        calls += 1
        raise ValueError("not transient")

    with pytest.raises(ValueError):
        fn()
    assert calls == 1


def test_retry_attempts_parameter() -> None:
    """The attempts parameter controls max total tries."""
    calls = 0

    @retry_with_backoff(attempts=5)
    def fn() -> str:
        nonlocal calls
        calls += 1
        raise httpx.TimeoutException("timed out")

    with pytest.raises(httpx.TimeoutException):
        fn()
    assert calls == 5
