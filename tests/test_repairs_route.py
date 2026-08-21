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

    assert repair["title"] == "Kitty's core service is unavailable"
    assert repair["fix"] == {
        "label": "Try again",
        "action_kind": "repair.check",
        "check_name": "service:gateway",
    }


def test_repair_payload_never_exposes_internal_setup_diagnostics() -> None:
    cases = [
        ("env:.env", "missing — copy .env.example to /Users/jacob/kitty/.env"),
        ("env:llm_key", "none of ['OPENAI_API_KEY'] set — models will fail"),
        (
            "runtime:venv",
            "no venv at /Users/jacob/kitty/venv — run: python3.11 -m venv venv "
            "&& venv/bin/pip install -r requirements.txt",
        ),
        ("service:gateway", "unreachable: http://127.0.0.1:8000/health — run: kitty up"),
    ]

    forbidden = (
        ".env",
        "/Users/",
        "OPENAI_API_KEY",
        "python3.11",
        "pip install",
        "127.0.0.1",
        "/health",
        "kitty up",
    )
    for name, detail in cases:
        repair = repairs._to_repair(SimpleNamespace(level="FAIL", name=name, detail=detail))
        fix_label = (repair.get("fix") or {}).get("label", "")
        visible = f"{repair['title']} {repair['detail']} {fix_label}"
        assert not any(token in visible for token in forbidden), visible


def test_repair_payload_sanitizes_category_diagnostics_without_marker_tokens() -> None:
    cases = [
        (
            "store:mem0",
            "memory client request failed with status code 503",
            "Memory search is unavailable right now.",
        ),
        (
            "codegraph:daemon",
            "daemon index handshake timed out after 30 seconds",
            "Search indexing needs attention.",
        ),
    ]

    for name, detail, expected_detail in cases:
        repair = repairs._to_repair(SimpleNamespace(level="WARN", name=name, detail=detail))

        assert repair["detail"] == expected_detail
        assert detail not in repair["detail"]


def test_public_infrastructure_repairs_use_product_language_only() -> None:
    cases = [
        (
            "service:gateway",
            "unreachable: http://127.0.0.1:8000/health",
            ("kitty", "core service", "try again"),
        ),
        (
            "env:gateway_secret",
            "missing KITTY_GATEWAY_SECRET — configure the gateway environment",
            ("kitty protection", "setup"),
        ),
        (
            "service:litellm",
            "unreachable: http://127.0.0.1:8001/health",
            ("model routing", "try again"),
        ),
        (
            "store:mem0",
            "memory client request failed with status code 503",
            ("memory search", "try again"),
        ),
        (
            "runtime:venv",
            "no venv at /Users/jacob/kitty/venv — run python3.11 -m venv venv",
            ("background service", "try again"),
        ),
        (
            "env:parse",
            "could not parse a setting from the environment",
            ("setup", "attention"),
        ),
        (
            "codegraph:daemon",
            "daemon index handshake timed out after 30 seconds",
            ("search indexing", "try again"),
        ),
    ]
    forbidden = ("gateway", "litellm", "mem0", "codegraph", "python", "venv", "environment")
    expected_titles = {
        "env:gateway_secret": "Kitty protection needs setup",
        "env:parse": "Some setup needs attention",
    }

    for name, detail, product_terms in cases:
        repair = repairs._to_repair(SimpleNamespace(level="WARN", name=name, detail=detail))
        fix_label = (repair.get("fix") or {}).get("label", "")
        visible = f"{repair['title']} {repair['detail']} {fix_label}".lower()

        if name in expected_titles:
            assert repair["title"] == expected_titles[name]
        assert not any(term in visible for term in forbidden), visible
        assert all(term in visible for term in product_terms), visible


def test_passing_checks_never_receive_failure_language() -> None:
    cases = [
        ("service:gateway", "reachable in 12ms", "Kitty's core service is responding."),
        ("service:litellm", "reachable in 10ms", "Model routing is responding."),
        ("store:mem0", "healthy", "Memory search is available."),
        ("runtime:venv", "ready", "Background services are ready."),
        ("codegraph:index", "fresh", "Search indexing is available."),
    ]

    for name, detail, expected_detail in cases:
        repair = repairs._to_repair(SimpleNamespace(level="PASS", name=name, detail=detail))
        assert repair["severity"] == "ok"
        assert repair["detail"] == expected_detail
        assert "unavailable" not in repair["detail"].lower()
        assert "needs attention" not in repair["detail"].lower()
