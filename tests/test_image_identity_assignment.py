from __future__ import annotations

import importlib

import pytest

from gateway.image_evaluation import ScorerResult
from scripts import image_lab_benchmark as bench


def _assignment():
    return importlib.import_module("gateway.image_identity_assignment")


def _expected(module):
    return [
        module.ExpectedIdentity("subject_1", "char_alex"),
        module.ExpectedIdentity("subject_2", "char_ben"),
    ]


def test_reversed_detection_order_still_matches_correct_characters() -> None:
    assignment = _assignment()
    detected = [
        assignment.DetectedIdentity("face_b", "subject_2"),
        assignment.DetectedIdentity("face_a", "subject_1"),
    ]
    result = assignment.score_identity_assignment(
        _expected(assignment),
        detected,
        [[0.20, 0.91], [0.89, 0.15]],
    )

    assert isinstance(result, ScorerResult)
    assert result.passed is True
    assert result.version == "identity-assignment@1"
    assert result.labels == []
    assert [(m["character_id"], m["detection_id"]) for m in result.score["matches"]] == [
        ("char_alex", "face_a"),
        ("char_ben", "face_b"),
    ]
    assert result.score["matches"][0]["margin"] == pytest.approx(0.71)


def test_identity_swap_fails_even_when_each_face_matches_strongly() -> None:
    assignment = _assignment()
    detected = [
        assignment.DetectedIdentity("face_a", "subject_2"),
        assignment.DetectedIdentity("face_b", "subject_1"),
    ]
    result = assignment.score_identity_assignment(
        _expected(assignment),
        detected,
        [[0.93, 0.10], [0.11, 0.92]],
    )

    assert result.passed is False
    assert any(label.startswith("identity_swap:") for label in result.labels)


def test_near_tie_is_identity_confusion_not_a_pass() -> None:
    assignment = _assignment()
    detected = [
        assignment.DetectedIdentity("face_a", "subject_1"),
        assignment.DetectedIdentity("face_b", "subject_2"),
    ]
    result = assignment.score_identity_assignment(
        _expected(assignment),
        detected,
        [[0.80, 0.78], [0.79, 0.81]],
        min_margin=0.05,
    )

    assert result.passed is False
    assert any(label.startswith("identity_confusion:") for label in result.labels)


def test_weak_assigned_identity_fails_threshold() -> None:
    assignment = _assignment()
    detected = [
        assignment.DetectedIdentity("face_a", "subject_1"),
        assignment.DetectedIdentity("face_b", "subject_2"),
    ]
    result = assignment.score_identity_assignment(
        _expected(assignment),
        detected,
        [[0.45, 0.10], [0.20, 0.44]],
        min_similarity=0.45,
    )

    assert result.passed is False
    assert "identity_below_threshold:subject_2" in result.labels


def test_exact_similarity_and_margin_thresholds_pass() -> None:
    assignment = _assignment()
    detected = [
        assignment.DetectedIdentity("face_a", "subject_1"),
        assignment.DetectedIdentity("face_b", "subject_2"),
    ]
    result = assignment.score_identity_assignment(
        _expected(assignment),
        detected,
        [[0.45, 0.40], [0.40, 0.45]],
        min_similarity=0.45,
        min_margin=0.05,
    )

    assert result.passed is True


@pytest.mark.parametrize(
    ("detected", "matrix", "expected_label"),
    [
        (["subject_1"], [[0.9], [0.2]], "missing_subjects"),
        (["subject_1", "subject_2", "extra"], [[0.9, 0.2, 0.1], [0.2, 0.9, 0.1]], "unexpected_subjects"),
    ],
)
def test_missing_or_extra_detected_people_fail_closed(detected, matrix, expected_label) -> None:
    assignment = _assignment()
    detected_subjects = [
        assignment.DetectedIdentity(f"face_{index}", slot)
        for index, slot in enumerate(detected, start=1)
    ]
    result = assignment.score_identity_assignment(_expected(assignment), detected_subjects, matrix)

    assert result.passed is False
    assert expected_label in result.labels


def test_malformed_similarity_matrix_is_infrastructure_failure() -> None:
    assignment = _assignment()
    detected = [
        assignment.DetectedIdentity("face_a", "subject_1"),
        assignment.DetectedIdentity("face_b", "subject_2"),
    ]
    with pytest.raises(assignment.IdentityAssignmentUnavailable, match="matrix"):
        assignment.score_identity_assignment(_expected(assignment), detected, [[0.9], [0.1]])


def test_assignment_is_deterministic_when_scores_tie() -> None:
    assignment = _assignment()
    detected = [
        assignment.DetectedIdentity("face_a", "subject_1"),
        assignment.DetectedIdentity("face_b", "subject_2"),
    ]
    kwargs = dict(min_similarity=0.0, min_margin=0.0)
    first = assignment.score_identity_assignment(
        _expected(assignment), detected, [[0.8, 0.8], [0.8, 0.8]], **kwargs
    )
    second = assignment.score_identity_assignment(
        _expected(assignment), detected, [[0.8, 0.8], [0.8, 0.8]], **kwargs
    )

    assert first.score == second.score


def test_stage_d_imagebench_consumes_structured_assignment_evidence(tmp_path) -> None:
    assignment = _assignment()
    image = tmp_path / "candidate.png"
    image.write_bytes(b"not-read-by-stub")
    scenario = next(
        item for item in bench.scenario_catalog() if item["scenario_id"] == "D.side_by_side"
    )
    detected = [
        assignment.DetectedIdentity("face_a", "subject_1"),
        assignment.DetectedIdentity("face_b", "subject_2"),
    ]
    assignment_result = assignment.score_identity_assignment(
        _expected(assignment), detected, [[0.91, 0.10], [0.11, 0.90]]
    )
    scorers = {
        name: (
            (lambda _path, result=assignment_result: result)
            if name == "assignment"
            else (lambda _path, name=name: ScorerResult(True, 0.9, f"{name}@1"))
        )
        for name in scenario["required_scorers"]
    }

    evidence = bench.evaluate_artifact_for_scenario(scenario, image, scorers=scorers)

    assert evidence["passed"] is True
    assert evidence["dimensions"]["assignment"]["matches"][0]["cast_slot"] == "subject_1"
    assert evidence["scorer_versions"]["assignment"] == "identity-assignment@1"


@pytest.mark.parametrize("slots", [["", "subject_2"], ["subject_1", "subject_1"]])
def test_detected_cast_slots_must_be_present_and_unique(slots) -> None:
    assignment = _assignment()
    detected = [
        assignment.DetectedIdentity("face_a", slots[0]),
        assignment.DetectedIdentity("face_b", slots[1]),
    ]

    with pytest.raises(assignment.IdentityAssignmentUnavailable, match="detected cast slots"):
        assignment.score_identity_assignment(
            _expected(assignment), detected, [[0.9, 0.1], [0.1, 0.9]]
        )
