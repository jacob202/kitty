"""Tests for the Council routing logic (no real model calls)."""

from __future__ import annotations

from gateway.council import (
    AGENT_CLAUDE,
    AGENT_DEEPSEEK,
    TaskDispatch,
    classify,
    council_route,
    decompose,
)


class FakeBackend:
    """Records dispatched tasks; returns a canned string. No network."""

    def __init__(self) -> None:
        self.calls: list[TaskDispatch] = []

    def run(self, agent: str, dispatch: TaskDispatch) -> str:
        self.calls.append(dispatch)
        return f"ok:{agent}:{dispatch.instructions[:20]}"

    def synthesize(self, question: str, parts: list, state: str) -> str:
        # Only pass usable (ok) outputs forward so a failed subtask can't poison
        # the merged answer — mirrors production behavior for the tests.
        ok_outs = [p.output for p in parts if p.ok]
        return " | ".join(ok_outs) if ok_outs else "[nothing usable]"


class ClarifyBackend(FakeBackend):
    """Every task returns a clarification non-answer (non-ok)."""

    def run(self, agent: str, dispatch: TaskDispatch) -> str:
        self.calls.append(dispatch)
        return "could you clarify what you mean?"


def test_classify_routes_coding_to_deepseek():
    assert classify("implement a function to parse json") == ("coding", AGENT_DEEPSEEK, "high")


def test_classify_routes_research_to_claude():
    assert classify("research the OpenAI SDK") == ("research", AGENT_CLAUDE, "medium")


def test_classify_routes_writing_to_claude():
    assert classify("write a doc explaining the design") == ("writing", AGENT_CLAUDE, "medium")


def test_classify_routes_codegen_to_deepseek():
    # Code-gen guard overrides the writing/coding tie.
    assert classify("write a python function to reverse a string") == ("coding", AGENT_DEEPSEEK, "high")


def test_decompose_splits_on_then():
    # v1 splits on newlines / 'then' / ';' — NOT 'and'.
    assert decompose("research X then implement Y") == ["research X", "implement Y"]


def test_council_route_dispatches_and_builds_dispatch():
    backend = FakeBackend()
    out = council_route("research X then implement Y", backend=backend)
    results = out.results

    assert len(results) == 2
    assert {r.assigned_to for r in results} == {AGENT_CLAUDE, AGENT_DEEPSEEK}
    # Every dispatch carried a self-contained TaskDispatch.
    assert all(isinstance(c, TaskDispatch) for c in backend.calls)
    assert all(c.priority in {"high", "medium", "low"} for c in backend.calls)


def test_council_route_binds_antecedents():
    backend = FakeBackend()
    council_route(
        "write a python script to parse csv then explain how it works",
        backend=backend,
    )
    # The referent-only 2nd segment must arrive bound to its predecessor.
    assert len(backend.calls) == 2
    second = backend.calls[1].instructions
    assert "previous task" in second
    assert "parse csv" in second


def test_council_route_semantic_ok_excludes_clarification():
    backend = ClarifyBackend()
    out = council_route("build a thing then refine it", backend=backend)
    results = out.results

    # Both subtasks returned clarifications -> neither is ok, and the answer
    # must not contain the clarification text.
    assert all(not r.ok for r in results)
    assert "clarify" not in out.answer


def test_council_route_routing_and_timings_present():
    backend = FakeBackend()
    out = council_route("research X then implement Y", backend=backend)

    assert len(out.routing) == 2
    assert out.routing[0].keys() >= {"task_id", "category", "agent", "priority"}
    assert len(out.timings) == 2
    assert out.timings[0].keys() >= {"task_id", "ms"}
    assert out.total_ms >= 0


def test_council_route_greeting_shortcircuits():
    backend = FakeBackend()
    out = council_route("hi", backend=backend)

    assert out.results == []          # no agent invoked
    assert backend.calls == []        # run never called
    assert "Hello" in out.answer
    assert out.routing == [] and out.timings == []


def test_council_route_marks_empty_output_failed():
    class EmptyBackend(FakeBackend):
        def run(self, agent: str, dispatch: TaskDispatch) -> str:
            return ""

    out = council_route("implement a thing", backend=EmptyBackend())
    assert out.results[0].ok is False
