"""QoL Packet 05 — Safe Self-Recovery.

Supervised recovery of Gateway background services: bounded exponential backoff,
retryable/non-retryable error classification, retry budget, cooldown, and
evidence. Recovery must never silently restart forever and must never touch
unrelated services.
"""

from __future__ import annotations

import asyncio

import pytest

from gateway.automation_supervisor import AutomationSupervisor, RecoveryPolicy, backoff_for


async def _wait_for(
    predicate,
    timeout: float = 2.0,
):
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        if predicate():
            return
        if asyncio.get_running_loop().time() >= deadline:
            raise AssertionError("condition never satisfied")
        await asyncio.sleep(0.005)


async def _wait_for_status(
    supervisor: AutomationSupervisor, name: str, wanted: set[str], timeout: float = 2.0
) -> dict:
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        status = supervisor.get_status(name)
        if status["status"] in wanted:
            return status
        if asyncio.get_running_loop().time() >= deadline:
            raise AssertionError(f"status never reached {wanted}: got {status}")
        await asyncio.sleep(0.005)


def test_backoff_is_exponential_and_bounded():
    policy = RecoveryPolicy(
        backoff_seconds=2.0,
        backoff_factor=5.0,
        backoff_max=60.0,
    )
    assert backoff_for(policy, 1) == 2.0
    assert backoff_for(policy, 2) == 10.0
    assert backoff_for(policy, 3) == 50.0
    assert backoff_for(policy, 4) == 60.0
    assert backoff_for(policy, 100) == 60.0


@pytest.mark.asyncio
async def test_transient_failure_recovers():
    supervisor = AutomationSupervisor()
    calls = 0
    hold = asyncio.Event()

    async def flaky():
        nonlocal calls
        calls += 1
        if calls == 1:
            raise ConnectionError("transient blip")
        await hold.wait()

    supervisor.track_recoverable(
        "svc",
        flaky,
        policy=RecoveryPolicy(max_attempts=3, backoff_seconds=0.01, backoff_factor=1.0),
    )
    await _wait_for(lambda: calls == 2)
    status = supervisor.get_status("svc")
    assert status["status"] == "available"
    evidence = supervisor.recovery_evidence("svc")
    assert evidence[-1]["outcome"] == "retrying"
    assert evidence[-1]["retryable"] is True
    assert "ConnectionError" in evidence[-1]["error"]
    await supervisor.stop_all()


@pytest.mark.asyncio
async def test_permanent_failure_stops_retrying():
    supervisor = AutomationSupervisor()
    calls = 0

    async def permanent():
        nonlocal calls
        calls += 1
        raise ValueError("bad configuration")

    supervisor.track_recoverable(
        "svc",
        permanent,
        policy=RecoveryPolicy(
            max_attempts=5,
            backoff_seconds=0.01,
            backoff_factor=1.0,
            non_retryable_errors=(ValueError,),
        ),
    )
    status = await _wait_for_status(supervisor, "svc", {"degraded"})
    assert status["status"] == "degraded"
    assert calls == 1
    evidence = supervisor.recovery_evidence("svc")
    assert evidence[-1]["outcome"] == "stopped"
    assert evidence[-1]["retryable"] is False
    assert status["recovery"]["cooldown_until"] is not None
    await supervisor.stop_all()


@pytest.mark.asyncio
async def test_retry_budget_respected():
    supervisor = AutomationSupervisor()
    calls = 0

    async def always_fails():
        nonlocal calls
        calls += 1
        raise ConnectionError("boom")

    supervisor.track_recoverable(
        "svc",
        always_fails,
        policy=RecoveryPolicy(max_attempts=3, backoff_seconds=0.01, backoff_factor=1.0),
    )
    status = await _wait_for_status(supervisor, "svc", {"degraded"})
    assert calls == 3
    evidence = supervisor.recovery_evidence("svc")
    assert evidence[-1]["outcome"] == "exhausted"
    assert status["recovery"]["cooldown_until"] is not None
    await asyncio.sleep(0.05)
    assert calls == 3
    await supervisor.stop_all()


@pytest.mark.asyncio
async def test_repeated_crash_becomes_degraded():
    supervisor = AutomationSupervisor()
    calls = 0

    async def crashing():
        nonlocal calls
        calls += 1
        raise RuntimeError("crash")

    supervisor.track_recoverable(
        "svc",
        crashing,
        policy=RecoveryPolicy(max_attempts=2, backoff_seconds=0.01, backoff_factor=1.0),
    )
    status = await _wait_for_status(supervisor, "svc", {"degraded"})
    assert status["status"] == "degraded"
    assert "exhausted" in status["reason"]
    await supervisor.stop_all()


@pytest.mark.asyncio
async def test_recovery_evidence_recorded():
    supervisor = AutomationSupervisor()
    calls = 0
    hold = asyncio.Event()

    async def flaky():
        nonlocal calls
        calls += 1
        if calls <= 2:
            raise OSError("flaky provider")
        await hold.wait()

    supervisor.track_recoverable(
        "svc",
        flaky,
        policy=RecoveryPolicy(max_attempts=4, backoff_seconds=0.01, backoff_factor=1.0),
    )
    await _wait_for(lambda: len(supervisor.recovery_evidence("svc")) == 2)
    evidence = supervisor.recovery_evidence("svc")
    assert len(evidence) == 2
    for entry in evidence:
        assert {"attempt", "error", "error_type", "retryable", "backoff", "outcome", "recorded_at"} <= set(entry)
        assert entry["outcome"] == "retrying"
    status = supervisor.get_status("svc")
    assert status["recovery"]["max_attempts"] == 4
    assert status["recovery"]["attempts"] == 2
    assert supervisor.snapshot()[0]["recovery"] is not None
    await supervisor.stop_all()


@pytest.mark.asyncio
async def test_failure_isolation_keeps_unrelated_service_healthy():
    supervisor = AutomationSupervisor()
    calls = 0
    healthy_hold = asyncio.Event()

    async def crashing():
        nonlocal calls
        calls += 1
        raise RuntimeError("crash")

    async def healthy():
        await healthy_hold.wait()

    healthy_task = asyncio.create_task(healthy())
    supervisor.track_task("healthy", healthy_task)
    supervisor.track_recoverable(
        "crashing",
        crashing,
        policy=RecoveryPolicy(max_attempts=2, backoff_seconds=0.01, backoff_factor=1.0),
    )
    await _wait_for_status(supervisor, "crashing", {"degraded"})
    assert supervisor.get_status("healthy")["status"] == "available"
    assert not healthy_task.cancelled()
    await supervisor.stop_all()


@pytest.mark.asyncio
async def test_restart_does_not_duplicate_work():
    supervisor = AutomationSupervisor()
    active = 0
    max_active = 0
    attempts = 0

    async def flaky():
        nonlocal active, max_active, attempts
        attempts += 1
        active += 1
        max_active = max(max_active, active)
        try:
            if attempts == 1:
                await asyncio.sleep(0.01)
                raise ConnectionError("blip")
            await asyncio.sleep(0.05)
        finally:
            active -= 1

    supervisor.track_recoverable(
        "svc",
        flaky,
        policy=RecoveryPolicy(max_attempts=3, backoff_seconds=0.01, backoff_factor=1.0),
    )
    await _wait_for(lambda: attempts == 2)
    await _wait_for_status(supervisor, "svc", {"available"})
    assert max_active == 1
    await supervisor.stop_all()


@pytest.mark.asyncio
async def test_shutdown_cancel_is_not_a_crash():
    supervisor = AutomationSupervisor()
    calls = 0
    hold = asyncio.Event()

    async def long_running():
        nonlocal calls
        calls += 1
        await hold.wait()

    supervisor.track_recoverable(
        "svc",
        long_running,
        policy=RecoveryPolicy(max_attempts=5, backoff_seconds=0.01, backoff_factor=1.0),
    )
    await _wait_for_status(supervisor, "svc", {"available"})
    await supervisor.stop_all()
    assert calls == 1
    await asyncio.sleep(0.05)
    assert calls == 1
    assert supervisor.get_status("svc")["status"] == "unavailable"
