import pytest

from src.memory.quarantine_queue import (
    MemoryCandidate,
    QuarantineQueue,
    QueueState,
)


def make_candidate(**overrides):
    data = {
        "candidate_id": "cand-1",
        "content": "Jacob prefers local-first memory",
        "category": "general",
        "source_evidence": ["docs/notes.md#12"],
    }
    data.update(overrides)
    return MemoryCandidate(**data)


def test_sensitive_and_personal_categories_default_to_review():
    queue = QuarantineQueue()

    sensitive = queue.stage(make_candidate(candidate_id="cand-s", category="sensitive"))
    personal = queue.stage(make_candidate(candidate_id="cand-p", category="personal"))

    assert sensitive.state is QueueState.REVIEW
    assert personal.state is QueueState.REVIEW


def test_general_candidate_stages_before_review():
    queue = QuarantineQueue()

    item = queue.stage(make_candidate())

    assert item.state is QueueState.STAGED
    assert queue.get(item.candidate_id).state is QueueState.STAGED


def test_approve_requires_source_evidence():
    queue = QuarantineQueue()
    staged = queue.stage(make_candidate(candidate_id="cand-no-evidence", source_evidence=[]))
    queue.review(staged.candidate_id)

    with pytest.raises(ValueError, match="source evidence"):
        queue.approve(staged.candidate_id)


def test_conflict_marked_candidate_defaults_to_review_and_blocks_approval():
    queue = QuarantineQueue()

    item = queue.stage(make_candidate(candidate_id="cand-conflict", conflict_marker=True))

    assert item.state is QueueState.REVIEW
    assert queue.get(item.candidate_id).conflict_marker is True

    with pytest.raises(ValueError, match="conflict"):
        queue.approve(item.candidate_id)


def test_review_then_approve_requires_clear_transition():
    queue = QuarantineQueue()

    item = queue.stage(make_candidate(candidate_id="cand-review"))

    with pytest.raises(ValueError, match="review"):
        queue.approve(item.candidate_id)

    reviewed = queue.review(item.candidate_id, note="looks good")
    assert reviewed.state is QueueState.REVIEW

    approved = queue.approve(item.candidate_id)
    assert approved.state is QueueState.APPROVED
    assert approved.promoted is True


def test_reject_and_retire_transitions():
    queue = QuarantineQueue()

    item = queue.stage(make_candidate(candidate_id="cand-reject"))
    reviewed = queue.review(item.candidate_id)
    rejected = queue.reject(reviewed.candidate_id, reason="contradictory")

    assert rejected.state is QueueState.REJECTED

    retired = queue.retire(rejected.candidate_id, reason="superseded")
    assert retired.state is QueueState.RETIRED


def test_clear_conflict_marker_allows_approval_after_review():
    queue = QuarantineQueue()

    item = queue.stage(make_candidate(candidate_id="cand-clear", conflict_marker=True))
    queue.clear_conflict_marker(item.candidate_id)
    queue.review(item.candidate_id)

    approved = queue.approve(item.candidate_id)

    assert approved.state is QueueState.APPROVED
    assert approved.conflict_marker is False
