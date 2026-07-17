"""Tenacity-based retry decorator with exponential backoff.

A single 429 from Gemini or DALL-E should not fail the whole call. With 3
attempts and exponential backoff (1-10s), transient rate-limit and service
errors recover. Retryable exceptions are logged at WARNING with the engine
name and attempt number — no payload dump (AGENTS.md prime directive).
"""

from __future__ import annotations

import logging
from typing import Callable, TypeVar

import httpx
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from mcp.imagen.logger import log

try:
    from google.api_core.exceptions import ResourceExhausted, ServiceUnavailable
except ImportError:  # pragma: no cover — google-api-core may not be installed in test env
    ResourceExhausted = type("ResourceExhausted", (Exception,), {})
    ServiceUnavailable = type("ServiceUnavailable", (Exception,), {})

T = TypeVar("T")

# Retry on rate-limit (429), service-down (503), and httpx-level transport errors.
_RETRYABLE = (
    ResourceExhausted,
    ServiceUnavailable,
    httpx.HTTPStatusError,
    httpx.TimeoutException,
    httpx.ConnectError,
)


def retry_with_backoff(attempts: int = 3) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator factory: retry transient failures with exponential backoff.

    Args:
        attempts: Max total attempts (including the first). Default 3.
    """
    return retry(
        stop=stop_after_attempt(attempts),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(_RETRYABLE),
        before_sleep=before_sleep_log(log, logging.WARNING),
        reraise=True,
    )
