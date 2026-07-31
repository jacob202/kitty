from __future__ import annotations

import inspect
from types import SimpleNamespace

from gateway import builder_queue
from gateway.routes import repairs


def test_repairs_route_runs_blocking_doctor_checks_off_the_event_loop() -> None:
    assert not inspect.iscoroutinefunction(repairs.list_repairs)


def test_builder_integrity_issue_is_not_reported_as_a_stale_lease(monkeypatch) -> None:
    monkeypatch.setattr(
        builder_queue,
        "find_silent_transitions",
        lambda: [{"id": "task-1"}, {"id": "task-2"}],
    )

    [check] = repairs._check_builder_health()

    assert check.level == "WARN"
    assert check.name == "builder:silent-transitions"
    assert "2 task(s) changed state without transition history" in check.detail
    assert "lease" not in check.detail.lower()


def test_gateway_failure_has_plain_language_and_a_recheck_action() -> None:
    repair = repairs._to_repair(
        SimpleNamespace(
            level="FAIL",
            name="service:gateway",
            detail="unreachable: http://127.0.0.1:8000/health",
        )
    )

    assert repair["title"] == "The Kitty gateway is not responding"
    assert repair["fix"] == {
        "label": "Check gateway again",
        "action_kind": "repair.check",
        "check_name": "service:gateway",
    }
