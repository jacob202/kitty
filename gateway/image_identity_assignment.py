"""Fail-closed identity assignment evidence for multi-character ImageBench runs."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import permutations
from math import isfinite
from typing import Sequence

from gateway.image_evaluation import ScorerResult

SCORER_VERSION = "identity-assignment@1"
_EPSILON = 1e-12


class IdentityAssignmentUnavailable(RuntimeError):
    """Raised when assignment evidence is malformed or cannot be evaluated."""


@dataclass(frozen=True)
class ExpectedIdentity:
    cast_slot: str
    character_id: str


@dataclass(frozen=True)
class DetectedIdentity:
    detection_id: str
    cast_slot: str


def _validate_subjects(
    expected: Sequence[ExpectedIdentity], detected: Sequence[DetectedIdentity]
) -> None:
    if not expected:
        raise IdentityAssignmentUnavailable("expected identities must not be empty")
    expected_slots = [item.cast_slot for item in expected]
    character_ids = [item.character_id for item in expected]
    detection_ids = [item.detection_id for item in detected]
    detected_slots = [item.cast_slot for item in detected]
    if any(not value for value in expected_slots + character_ids + detection_ids):
        raise IdentityAssignmentUnavailable("identity assignment ids must be non-empty")
    if len(set(expected_slots)) != len(expected_slots):
        raise IdentityAssignmentUnavailable("expected cast slots must be unique")
    if len(set(character_ids)) != len(character_ids):
        raise IdentityAssignmentUnavailable("expected character ids must be unique")
    if len(set(detection_ids)) != len(detection_ids):
        raise IdentityAssignmentUnavailable("detected identity ids must be unique")
    if any(not value for value in detected_slots) or len(set(detected_slots)) != len(detected_slots):
        raise IdentityAssignmentUnavailable("detected cast slots must be present and unique")


def _validate_matrix(
    matrix: Sequence[Sequence[float]], expected_count: int, detected_count: int
) -> list[list[float]]:
    if len(matrix) != expected_count:
        raise IdentityAssignmentUnavailable("similarity matrix row count is invalid")
    normalized: list[list[float]] = []
    for row in matrix:
        if len(row) != detected_count:
            raise IdentityAssignmentUnavailable("similarity matrix column count is invalid")
        normalized_row: list[float] = []
        for value in row:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise IdentityAssignmentUnavailable("similarity matrix must be numeric")
            number = float(value)
            if not isfinite(number) or number < -1.0 or number > 1.0:
                raise IdentityAssignmentUnavailable("similarity matrix contains invalid values")
            normalized_row.append(number)
        normalized.append(normalized_row)
    return normalized


def _count_failure(expected_count: int, detected_count: int) -> ScorerResult:
    if detected_count < expected_count:
        labels = ["missing_subjects"]
    else:
        labels = ["unexpected_subjects"]
    return ScorerResult(
        passed=False,
        score={
            "expected_subjects": expected_count,
            "detected_subjects": detected_count,
            "matches": [],
        },
        version=SCORER_VERSION,
        labels=labels,
    )


def score_identity_assignment(
    expected: Sequence[ExpectedIdentity],
    detected: Sequence[DetectedIdentity],
    similarity_matrix: Sequence[Sequence[float]],
    *,
    min_similarity: float = 0.45,
    min_margin: float = 0.05,
) -> ScorerResult:
    """Match expected identities to detected people and fail closed on ambiguity."""
    if isinstance(min_similarity, bool) or not isinstance(min_similarity, (int, float)):
        raise IdentityAssignmentUnavailable("min_similarity must be numeric")
    if isinstance(min_margin, bool) or not isinstance(min_margin, (int, float)):
        raise IdentityAssignmentUnavailable("min_margin must be numeric")
    min_similarity = float(min_similarity)
    min_margin = float(min_margin)
    if not isfinite(min_similarity) or not -1.0 <= min_similarity <= 1.0:
        raise IdentityAssignmentUnavailable("min_similarity is out of range")
    if not isfinite(min_margin) or min_margin < 0.0:
        raise IdentityAssignmentUnavailable("min_margin must be non-negative")

    expected = tuple(expected)
    detected = tuple(detected)
    _validate_subjects(expected, detected)
    matrix = _validate_matrix(similarity_matrix, len(expected), len(detected))
    if len(expected) != len(detected):
        return _count_failure(len(expected), len(detected))
    ranked: list[tuple[float, tuple[int, ...]]] = []
    for permutation in permutations(range(len(detected))):
        total = sum(matrix[row][column] for row, column in enumerate(permutation))
        ranked.append((total, permutation))
    ranked.sort(key=lambda item: (-item[0], item[1]))
    best_total, best = ranked[0]

    labels: list[str] = []
    matches: list[dict[str, object]] = []
    for row, column in enumerate(best):
        expected_identity = expected[row]
        detected_identity = detected[column]
        similarity = matrix[row][column]
        alternatives = [value for index, value in enumerate(matrix[row]) if index != column]
        runner_up = max(alternatives) if alternatives else -1.0
        margin = similarity - runner_up

        if similarity + _EPSILON < min_similarity:
            labels.append(f"identity_below_threshold:{expected_identity.cast_slot}")
        if margin + _EPSILON < min_margin:
            labels.append(f"identity_confusion:{expected_identity.cast_slot}")
        if detected_identity.cast_slot != expected_identity.cast_slot:
            labels.append(
                f"identity_swap:{expected_identity.cast_slot}->{detected_identity.cast_slot}"
            )
        matches.append(
            {
                "cast_slot": expected_identity.cast_slot,
                "character_id": expected_identity.character_id,
                "detection_id": detected_identity.detection_id,
                "detected_cast_slot": detected_identity.cast_slot,
                "similarity": similarity,
                "runner_up_similarity": runner_up,
                "margin": margin,
            }
        )

    return ScorerResult(
        passed=not labels,
        score={
            "expected_subjects": len(expected),
            "detected_subjects": len(detected),
            "matches": matches,
            "assignment_total_similarity": best_total,
            "assignment_mean_similarity": best_total / len(expected),
        },
        version=SCORER_VERSION,
        labels=labels,
    )
