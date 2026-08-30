"""LLM call observability.

Lane E foundation: every chat call leaves a JSONL trail at
``data/llm_calls.jsonl`` with the timestamp, model, latency,
outcome, and any error message. This is the minimum useful
visibility into LLM usage — a backfill for the existing
``log_chat_trace`` which only records routing decisions, not call
outcomes.

Why a separate file (and not just adding to the existing
``log_chat_trace``): the existing trace is per-routing-decision
and lives in different files. The observability file is
per-call and aggregated. The two are complementary, not
duplicates.

Why JSONL not SQLite: append-only writes, no migration cost,
one line per call, easy to grep / jq / tail. If we ever need
to query aggregates, the same data is small enough to load
into a notebook.

Failure mode: the recording function is best-effort. If the
file can't be written, we log a warning and continue — never
break a chat call because the observability file is locked.
"""

from __future__ import annotations

import json
import logging
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterator

from gateway.paths import DATA_DIR

logger = logging.getLogger("kitty.observability")

DEFAULT_LOG_PATH = DATA_DIR / "llm_calls.jsonl"


@dataclass
class ChatCall:
    """One LLM call, recorded as a single JSONL line."""

    timestamp: float
    model: str
    latency_ms: float
    success: bool
    error: str | None = None
    operation: str = "llm.call"
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    correlation_id: str | None = None


@contextmanager
def record_chat(
    model: str,
    *,
    operation: str = "llm.call",
    correlation_id: str | None = None,
    log_path: Path = DEFAULT_LOG_PATH,
) -> Iterator[ChatCall]:
    """Context manager that times a chat call and appends a JSONL line on exit.

    Usage::

        with record_chat("kitty-sonnet", operation="brief.synthesis") as call:
            response = call_llm(messages, model="kitty-sonnet")
            call.prompt_tokens = _estimate_tokens(messages)
            call.completion_tokens = _estimate_tokens([response])

    The returned ``call`` object is mutable so the caller can fill
    in token counts after the call returns. The JSONL line is
    written at context exit, regardless of whether the body
    raised.
    """
    call = ChatCall(
        timestamp=time.time(),
        model=model,
        latency_ms=0.0,
        success=True,
        operation=operation,
        correlation_id=correlation_id,
    )
    start = time.monotonic()
    try:
        yield call
    except BaseException as exc:
        call.success = False
        call.error = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        call.latency_ms = round((time.monotonic() - start) * 1000, 1)
        _append_call(call, log_path)


def _append_call(call: ChatCall, log_path: Path) -> None:
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(call), default=str) + "\n")
    except OSError as exc:
        logger.warning("observability: failed to append to %s: %s", log_path, exc)
