"""Tests for the Council routing logic (no real model calls)."""

from __future__ import annotations

from gateway.council import (
    AGENT_CLAUDE,
    AGENT_DEEPSEEK,
    TaskDispatch,
    classify,
    council_route,
    decompose,
    is_trivial,
)


class FakeBackend:
    """Records dispatched tasks; returns a canned string. No network."""

    def __init__(self) -> None:
        self.calls: list[TaskDispatch] = []

    def run(self, agent: str, dispatch: TaskDispatch) -> str:
        self.calls.append(dispatch)
        return f"ok:{agent}:{dispatch.instructions[:20]}"


def test_classify_routes_coding_to_deepseek():
    assert classify("implement a function to parse json") == ("coding", AGENT_DEEPSEEK, "high")


def test_classify_routes_research_to_claude():
    assert classify("research the OpenAI SDK") == ("research", AGENT_CLAUDE, "medium")


def test_classify_routes_writing_to_claude():
    assert classify("write a doc explaining the design") == ("writing", AGENT_CLAUDE, "medium")


def test_is_trivial_true_for_what_questions():
    assert is_trivial("what port is the gateway on")
    assert not is_trivial("implement a new route")


def test_decompose_splits_on_and():
    assert decompose("research X and implement Y") == ["research X", "implement Y"]


def test_council_route_dispatches_and_builds_dispatch():
    backend = FakeBackend()
    results = council_route("research the API and implement a parser", backend=backend)

    assert len(results) == 2
    assert {r.assigned_to for r in results} == {AGENT_CLAUDE, AGENT_DEEPSEEK}
    # Every dispatch carried a self-contained TaskDispatch.
    assert all(isinstance(c, TaskDispatch) for c in backend.calls)
    assert all(c.priority in {"high", "medium", "low"} for c in backend.calls)


def test_council_route_handles_trivial_inline():
    backend = FakeBackend()
    results = council_route("what port is the gateway on", backend=backend)

    assert len(results) == 1
    assert results[0].assigned_to == "council"  # inline, not dispatched
    assert backend.calls == []  # no agent invoked


def test_council_route_marks_empty_output_failed():
    class EmptyBackend(FakeBackend):
        def run(self, agent: str, dispatch: TaskDispatch) -> str:
            return ""

    results = council_route("implement a thing", backend=EmptyBackend())
    assert results[0].ok is False
