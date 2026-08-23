"""Tests for mcp.imagen.retry — tenacity decorator retries transient failures."""

from __future__ import annotations

import httpx
import pytest

from mcp.imagen.retry import retry_with_backoff


def _disable_real_sleep(fn) -> None:
    """Exercise Tenacity retry logic without paying real backoff wall time."""
    fn.retry.sleep = lambda _seconds: None


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

    _disable_real_sleep(fn)
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

    _disable_real_sleep(fn)
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

    _disable_real_sleep(fn)
    with pytest.raises(httpx.TimeoutException):
        fn()
    assert calls == 5


def test_retry_backoff_schedule_is_exponential_and_capped() -> None:
    """Backoff remains 1, 2, 4, 8 seconds before capping at 10 seconds."""

    @retry_with_backoff(attempts=6)
    def fn() -> str:
        return "unused"

    class RetryState:
        def __init__(self, attempt_number: int) -> None:
            self.attempt_number = attempt_number

    waits = [fn.retry.wait(RetryState(attempt)) for attempt in range(1, 7)]
    assert waits == [1.0, 2, 4, 8, 10.0, 10.0]
