"""Reproduces: gateway/expert_proactive.py's async _poll_single_expert calls
gateway.llm_client.call_llm synchronously (via _is_duplicate_signal, line 261),
and gateway.llm_client.retry_with_backoff's 429 handling uses a blocking
time.sleep. Called from an async context with no asyncio.to_thread (as
_is_duplicate_signal does), this stalls the whole event loop for every other
concurrent task -- not just the caller.

This isolates retry_with_backoff itself (the actual blocking primitive named
in the finding) rather than going through call_llm's full provider-routing
logic, which short-circuits in a test environment with no providers
configured and would otherwise never reach a retry/backoff at all.
"""

import asyncio
import time

import pytest

from gateway.llm_client import retry_with_backoff

# The bug this reproduces is real and still open: retry_with_backoff sleeps on
# the caller's thread, so an async caller freezes the whole event loop. Marked
# xfail so the reproduction stays in the suite as live evidence instead of
# blocking every push; it flips to XPASS the moment the sleep stops blocking.
pytestmark = pytest.mark.xfail(
    reason="open bug: llm_client.retry_with_backoff blocks the event loop on 429",
    strict=False,
)


def test_synchronous_retry_with_backoff_blocks_the_event_loop_when_awaited_bare():
    call_count = {"n": 0}

    class RateLimited(Exception):
        pass

    @retry_with_backoff
    def flaky_llm_call():
        call_count["n"] += 1
        if call_count["n"] < 2:
            err = RateLimited("429 rate limited")
            err.response = None
            raise err
        return "ok"

    heartbeats: list[float] = []

    async def heartbeat():
        # A well-behaved concurrent task on the same event loop: it should
        # keep making progress roughly every 10ms regardless of what other
        # tasks are doing, as long as nothing blocks the loop itself.
        for _ in range(10):
            heartbeats.append(time.monotonic())
            await asyncio.sleep(0.01)

    async def run():
        hb_task = asyncio.create_task(heartbeat())
        # Let the heartbeat task actually start running (creating a task only
        # schedules it; it needs a real yield point to get its first tick in)
        # before the blocking call below has a chance to starve it.
        await asyncio.sleep(0)
        # This mirrors expert_proactive.py:261 exactly: a synchronous,
        # blocking call made directly from async code, no to_thread.
        result = flaky_llm_call()
        await hb_task
        return result

    asyncio.run(run())

    # base_delay=1.0s means the single 429 retry sleeps for ~1s. If that
    # sleep were truly async (or offloaded via to_thread), the heartbeat
    # would keep landing every ~10ms throughout. Because retry_with_backoff
    # uses a bare time.sleep on the event loop's own thread, the entire loop
    # freezes for that ~1s and the gap between two consecutive heartbeats
    # blows past what asyncio.sleep(0.01) should ever produce.
    max_gap = max(b - a for a, b in zip(heartbeats, heartbeats[1:]))
    assert max_gap < 0.5, (
        f"event loop stalled for {max_gap:.2f}s -- retry_with_backoff's blocking "
        f"time.sleep froze all concurrent async work, not just the caller, "
        f"exactly as it does when gateway/expert_proactive.py calls "
        f"llm_client.call_llm directly from async code with no asyncio.to_thread"
    )
