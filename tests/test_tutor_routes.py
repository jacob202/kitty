"""Route-level tests for the Tutor HTTP surface (DTH-03/04 wiring)."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from gateway import tutor
from gateway.app import app


@pytest.fixture(autouse=True)
def _temp_memory_db(tmp_path: Path):
    """Keep tests from writing to the real tutor_memory.db."""
    original = tutor.MEMORY_DB
    tutor.MEMORY_DB = tmp_path / "tutor_memory.db"
    yield
    tutor.MEMORY_DB = original


@pytest.fixture
def client():
    return TestClient(app)


def test_grade_choice_route(client):
    r = client.post(
        "/tutor/grade",
        json={"user_answer": "b", "expected_answer": "B", "question_type": "choice"},
    )
    assert r.status_code == 200
    assert r.json() == {"correct": True}


def test_grade_rejects_unknown_question_type(client):
    r = client.post(
        "/tutor/grade",
        json={"user_answer": "x", "expected_answer": "y", "question_type": "essay"},
    )
    assert r.status_code == 400
    assert "question_type" in r.text


def test_attempt_records_mastery_and_stage(client):
    r = client.post(
        "/tutor/attempt",
        json={"term": "refactor", "correct": True, "kp_type": "concept"},
    )
    assert r.status_code == 200
    payload = r.json()
    # CONCEPT passes map to full mastery on a correct answer (DTH-04 gates).
    assert payload["mastery"] == 1.0
    assert payload["stage"] == "mastered"
    assert payload["next_action"] == "complete"


def test_attempt_rejects_unknown_kp_type(client):
    r = client.post(
        "/tutor/attempt",
        json={"term": "refactor", "correct": True, "kp_type": "vibes"},
    )
    assert r.status_code == 400
    assert "kp_type" in r.text


def test_quiz_empty_when_fewer_than_two_terms_due(client):
    r = client.get("/tutor/quiz")
    assert r.status_code == 200
    assert r.json() == {"questions": [], "due": 0}


def test_quiz_builds_deterministic_questions_from_due_terms(client):
    # A wrong answer schedules review 0-3 days out; MEMORY wrong -> 0 days,
    # i.e. due immediately.
    for term in ("alpha", "beta", "gamma"):
        client.post("/tutor/attempt", json={"term": term, "correct": False})

    r = client.get("/tutor/quiz")
    assert r.status_code == 200
    payload = r.json()
    assert payload["due"] == 3
    assert len(payload["questions"]) == 3
    q = payload["questions"][0]
    assert set(q) == {"question", "options", "answer_label"}
    assert len(q["options"]) == 3


def test_term_status_route(client):
    client.post("/tutor/attempt", json={"term": "delta", "correct": False})
    r = client.get("/tutor/term/delta")
    assert r.status_code == 200
    payload = r.json()
    assert payload["stage"] == "learning"
    assert payload["next_action"] == "practice"
    assert 0.0 <= payload["mastery"] < 1.0

    fresh = client.get("/tutor/term/never-seen").json()
    assert fresh["stage"] == "new"
    assert fresh["next_action"] == "probe"
