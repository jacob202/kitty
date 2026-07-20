"""Tests for the Kitty Tutor module.

Retrieval and the LLM are injected so these run without ChromaDB or Ollama.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from gateway import tutor


@pytest.fixture(autouse=True)
def _temp_memory_db(tmp_path: Path):
    """Keep tests from writing to the real tutor_memory.db."""
    tutor.MEMORY_DB = tmp_path / "tutor_memory.db"
    yield


def _run(coro):
    return asyncio.run(coro)


GOOD_LLM = (
    '{"vocab": ["refactor", "behavior", "structure"], '
    '"explain": "It is like reorganizing a toolbox without losing any tools.", '
    '"question": "Why avoid changing behavior during a refactor?"}'
)


def test_ask_returns_vocab_first_and_question():
    async def retr(_: str) -> list[str]:
        return ["Refactoring restructures code without changing behavior."]

    ans = _run(tutor.ask("refactoring", retriever=retr, llm=lambda _m: GOOD_LLM))
    assert ans["vocab"], "expected vocab terms"
    assert len(ans["vocab"]) == 3
    assert ans["question"], "expected a check-in question"


def test_ask_with_no_docs_refuses_and_points_to_learn():
    async def empty(_: str) -> list[str]:
        return []

    try:
        _run(tutor.ask("quantum entanglement", retriever=empty, llm=lambda _m: "{}"))
    except tutor.TutorError as exc:
        assert "kitty tutor learn" in str(exc)
    else:
        raise AssertionError("expected TutorError on empty retrieval")


def test_ask_non_json_llm_fails_loud():
    async def retr(_: str) -> list[str]:
        return ["some context"]

    try:
        _run(tutor.ask("x", retriever=retr, llm=lambda _m: "Sure! Here is the answer."))
    except tutor.TutorError:
        pass
    else:
        raise AssertionError("expected TutorError on non-JSON LLM output")


def test_confidence_spacing():
    tutor.log_confidence("refactor", 1)
    assert all(d["term"] != "refactor" for d in tutor.due_review())

    tutor.log_confidence("refactor", 3)
    due = tutor.due_review()
    assert any(d["term"] == "refactor" for d in due)


def test_log_confidence_rejects_bad_score():
    try:
        tutor.log_confidence("x", 9)
    except tutor.TutorError:
        pass
    else:
        raise AssertionError("expected TutorError on invalid score")


def test_log_confidence_rejects_bad_knowledge_type():
    try:
        tutor.log_confidence("x", 1, knowledge_type="bogus")
    except tutor.TutorError:
        pass
    else:
        raise AssertionError("expected TutorError on invalid knowledge_type")


def test_type_specific_intervals():
    # CONCEPT score 1 schedules 7 days out; not due immediately.
    tutor.log_confidence("design-pattern", 1, knowledge_type=tutor.KnowledgeType.CONCEPT)
    assert all(d["term"] != "design-pattern" for d in tutor.due_review())

    # CONCEPT score 3 is due next session (0 days).
    tutor.log_confidence("design-pattern", 3, knowledge_type=tutor.KnowledgeType.CONCEPT)
    due = tutor.due_review()
    assert any(d["term"] == "design-pattern" for d in due)


def test_memory_interval_preserved():
    # Default MEMORY type keeps the original {1: 3, 2: 1, 3: 0} behavior.
    tutor.log_confidence("term-x", 1)
    assert all(d["term"] != "term-x" for d in tutor.due_review())
    tutor.log_confidence("term-x", 3)
    assert any(d["term"] == "term-x" for d in tutor.due_review())


def test_grade_choice_exact():
    assert tutor.grade_answer("B", "b", question_type="choice")
    assert not tutor.grade_answer("A", "B", question_type="choice")


def test_grade_short_similarity():
    assert tutor.grade_answer("analyse", "analyze", question_type="short")
    assert not tutor.grade_answer("completely different", "refactoring", question_type="short")


def test_grade_open_keyword_overlap():
    assert tutor.grade_answer(
        "refactoring preserves behavior", "refactoring preserves behavior", question_type="open"
    )
    assert not tutor.grade_answer("unrelated text here", "refactoring preserves behavior", question_type="open")
