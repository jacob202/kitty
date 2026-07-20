"""Tests for DTH-04: Mastery gates + learning stages."""

from __future__ import annotations

from pathlib import Path

import pytest

from gateway import tutor


@pytest.fixture(autouse=True)
def _temp_db(tmp_path: Path):
    """Keep tests from writing to the real tutor DB."""
    tutor.MEMORY_DB = tmp_path / "tutor_memory.db"
    yield


# ── compute_mastery ──────────────────────────────────────────────────────────


class TestComputeMastery:
    def test_empty(self):
        assert tutor.compute_mastery([]) == 0.0

    def test_single_correct_capped(self):
        # 1 attempt → confidence cap 0.5
        assert tutor.compute_mastery([True]) == 0.5

    def test_two_correct_capped(self):
        # 2 attempts → confidence cap 0.8
        assert tutor.compute_mastery([True, True]) == 0.8

    def test_three_correct_uncapped(self):
        # 3 attempts → no cap, recency-weighted: (0.85*1 + 0.95*1 + 1.0*1) / (0.85+0.95+1.0)
        result = tutor.compute_mastery([True, True, True])
        assert result == pytest.approx(1.0)

    def test_mixed_early_wrong(self):
        # First attempt wrong, next correct → recovery after early mistakes
        result = tutor.compute_mastery([False, True, True, True, True])
        # Last 5: [F, T, T, T, T] → weights [0.5, 0.7, 0.85, 0.95, 1.0]
        expected = (0.5 * 0 + 0.7 * 1 + 0.85 * 1 + 0.95 * 1 + 1.0 * 1) / (
            0.5 + 0.7 + 0.85 + 0.95 + 1.0
        )
        assert result == pytest.approx(expected)

    def test_all_wrong(self):
        assert tutor.compute_mastery([False, False, False]) == 0.0

    def test_many_attempts_stays_at_one(self):
        # Once you have enough correct, mastery stays at 1.0
        assert tutor.compute_mastery([True] * 10) == 1.0


# ── LearningStage ────────────────────────────────────────────────────────────


class TestLearningStage:
    def test_enum_values(self):
        assert tutor.LearningStage.NEW.value == "new"
        assert tutor.LearningStage.LEARNING.value == "learning"
        assert tutor.LearningStage.MASTERED.value == "mastered"


# ── log_attempt ──────────────────────────────────────────────────────────────


class TestLogAttempt:
    def test_first_attempt_returns_low_mastery(self):
        mastery = tutor.log_attempt("kubernetes", True, tutor.KnowledgeType.MEMORY)
        assert 0 < mastery <= 0.5

    def test_stores_in_db(self):
        tutor.log_attempt("docker", True, tutor.KnowledgeType.MEMORY)
        assert tutor.mastery_of("docker") > 0

    def test_incorrect_returns_zero_mastery(self):
        mastery = tutor.log_attempt("pod", False, tutor.KnowledgeType.MEMORY)
        assert mastery == 0.0

    def test_concept_correct_sets_full_mastery(self):
        # Qualitative types: correct → mastery = 1.0
        mastery = tutor.log_attempt(
            "abstraction", True, tutor.KnowledgeType.CONCEPT
        )
        assert mastery == 1.0

    def test_design_correct_sets_full_mastery(self):
        mastery = tutor.log_attempt(
            "architecture", True, tutor.KnowledgeType.DESIGN
        )
        assert mastery == 1.0

    def test_rejects_invalid_kp_type(self):
        with pytest.raises(tutor.TutorError, match="kp_type must be"):
            tutor.log_attempt("x", True, kp_type="bogus")


# ── mastery_of ───────────────────────────────────────────────────────────────


class TestMasteryOf:
    def test_unknown_term(self):
        assert tutor.mastery_of("nonexistent") == 0.0

    def test_after_attempt(self):
        tutor.log_attempt("redis", True, tutor.KnowledgeType.MEMORY)
        assert tutor.mastery_of("redis") > 0


# ── is_mastered ──────────────────────────────────────────────────────────────


class TestIsMastered:
    def test_new_not_mastered(self):
        assert not tutor.is_mastered("new-term", tutor.KnowledgeType.MEMORY)

    def test_concept_needs_perfect(self):
        tutor.log_attempt("abstraction", True, tutor.KnowledgeType.CONCEPT)
        assert tutor.is_mastered("abstraction", tutor.KnowledgeType.CONCEPT)

    def test_memory_needs_gate(self):
        # MEMORY gate is 0.9 — one correct (capped at 0.5) doesn't clear it
        tutor.log_attempt("redis", True, tutor.KnowledgeType.MEMORY)
        assert not tutor.is_mastered("redis", tutor.KnowledgeType.MEMORY)


# ── stage_of ─────────────────────────────────────────────────────────────────


class TestStageOf:
    def test_new(self):
        assert tutor.stage_of("never-seen") == tutor.LearningStage.NEW

    def test_learning(self):
        tutor.log_attempt("pod", False, tutor.KnowledgeType.MEMORY)
        assert tutor.stage_of("pod") == tutor.LearningStage.LEARNING

    def test_mastered(self):
        tutor.log_attempt(
            "abstraction", True, tutor.KnowledgeType.CONCEPT
        )
        assert tutor.stage_of("abstraction", tutor.KnowledgeType.CONCEPT) == tutor.LearningStage.MASTERED


# ── next_action ──────────────────────────────────────────────────────────────


class TestNextAction:
    def test_probe_new(self):
        assert tutor.next_action("never-seen") == "probe"

    def test_practice_memory_below_gate(self):
        tutor.log_attempt("redis", True, tutor.KnowledgeType.MEMORY)
        assert tutor.next_action("redis", tutor.KnowledgeType.MEMORY) == "practice"

    def test_assess_concept_below_gate(self):
        tutor.log_attempt("abstraction", False, tutor.KnowledgeType.CONCEPT)
        assert tutor.next_action("abstraction", tutor.KnowledgeType.CONCEPT) == "assess"

    def test_complete_mastered(self):
        tutor.log_attempt(
            "abstraction", True, tutor.KnowledgeType.CONCEPT
        )
        assert tutor.next_action("abstraction", tutor.KnowledgeType.CONCEPT) == "complete"


# ── build_choice_question ────────────────────────────────────────────────────


class TestBuildChoiceQuestion:
    def test_basic(self):
        q = tutor.build_choice_question("What is 2+2?", "4", ["3", "5", "6"])
        assert q["question"] == "What is 2+2?"
        assert len(q["options"]) == 4
        assert q["answer_label"] in ("A", "B", "C", "D")
        # The answer body appears in the options
        answer_body = next(
            opt.split(": ", 1)[1]
            for opt in q["options"]
            if opt.startswith(q["answer_label"] + ":")
        )
        assert answer_body == "4"

    def test_deterministic_order(self):
        q1 = tutor.build_choice_question("Q", "answer", ["x", "y"])
        q2 = tutor.build_choice_question("Q", "answer", ["x", "y"])
        assert q1["options"] == q2["options"]

    def test_empty_answer_raises(self):
        with pytest.raises(tutor.TutorError, match="non-empty answer"):
            tutor.build_choice_question("Q", "", ["x"])

    def test_no_distractors_raises(self):
        with pytest.raises(tutor.TutorError, match="at least one distractor"):
            tutor.build_choice_question("Q", "answer", [])


# ── generate_recall_quiz ─────────────────────────────────────────────────────


class TestGenerateRecallQuiz:
    def test_basic(self):
        qs = tutor.generate_recall_quiz(["alpha", "beta", "gamma"])
        assert len(qs) == 3
        for q in qs:
            assert len(q["options"]) == 3

    def test_needs_two_terms(self):
        with pytest.raises(tutor.TutorError, match="at least two terms"):
            tutor.generate_recall_quiz(["only-one"])

    def test_filters_empty(self):
        qs = tutor.generate_recall_quiz(["a", "b", ""])
        assert len(qs) == 2
