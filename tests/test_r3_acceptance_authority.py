from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import HTTPException

from gateway import memory_mission, mission_runtime
from gateway.routes import missions as mission_routes


def _verifying_mission(db_path: Path, *, mission_id: str = "r3-acceptance") -> dict:
    memory_mission.create_mission(
        mission_id=mission_id,
        objective="Accept one exact running result",
        definition_of_done=["The running journey is independently accepted."],
        supervisor_id="kitty",
        db_path=db_path,
    )
    memory_mission.bind_builder_locator(
        mission_id,
        initiative_id="builder-initiative-1",
        task_id="builder-task-1",
        db_path=db_path,
    )
    memory_mission.set_plan(
        mission_id,
        plan_ref="docs/plan.md@" + "a" * 40,
        plan_digest="b" * 64,
        db_path=db_path,
    )
    memory_mission.record_plan_review(
        mission_id,
        reviewer_id="independent-plan-reviewer",
        plan_digest="b" * 64,
        verdict="approved",
        db_path=db_path,
    )
    memory_mission.begin_execution(mission_id, db_path=db_path)
    return memory_mission.get_mission(mission_id, db_path=db_path)


def _candidate(*, review_sha: str = "d" * 40) -> dict[str, str]:
    base = {
        "artifact_id": "builder_result_builder-task-1_attempt-7",
        "content_hash": "c" * 64,
        "review_sha": review_sha,
        "diff_sha256": "e" * 64,
    }
    return {**base, "candidate_digest": mission_runtime._candidate_provenance_digest(base)}


def _passing_evidence() -> dict:
    evidence = {
        "steps": ["Chat request", "Mission approval", "Builder result", "Library reuse", "Chat reuse"],
        "unmet_gates": [],
    }
    for key in mission_runtime._REQUIRED_RUNNING_STATES:
        evidence[key] = {"state": "passed", "evidence": f"evidence://{key}"}
    return evidence


def test_candidate_digest_changes_when_review_revision_changes() -> None:
    first = _candidate(review_sha="d" * 40)
    second = _candidate(review_sha="f" * 40)

    assert first["content_hash"] == second["content_hash"]
    assert first["candidate_digest"] != second["candidate_digest"]


def test_production_http_acceptance_is_not_authoritative(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(mission_routes, "is_test_env", lambda: False)
    body = mission_routes.AcceptanceRequest(
        reviewer_id="caller-controlled",
        candidate_digest="c" * 64,
        verdict="accepted",
        evidence={"anything": True},
    )

    with pytest.raises(HTTPException) as exc_info:
        mission_routes.record_acceptance("mission-any", body)

    assert exc_info.value.status_code == 403


def test_local_operator_stamps_trusted_identity_and_exact_provenance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "kitty.db"
    monkeypatch.setattr(memory_mission, "MISSION_DB_FILE", db_path)
    _verifying_mission(db_path)
    candidate = _candidate()
    candidate_ref = f"artifact:{candidate['artifact_id']}"
    memory_mission.record_candidate(
        "r3-acceptance",
        candidate_ref=candidate_ref,
        candidate_digest=candidate["candidate_digest"],
        db_path=db_path,
    )
    monkeypatch.setattr(mission_runtime, "_reviewed_builder_result", lambda mission: candidate)
    monkeypatch.setattr(mission_runtime.repo_tools, "repo_head", lambda: "f" * 40)
    isolated_data = tmp_path / "isolated-data"
    monkeypatch.setattr(mission_runtime, "DATA_DIR", isolated_data)

    accepted = mission_runtime.record_running_product_acceptance(
        "r3-acceptance",
        candidate_ref=candidate_ref,
        candidate_digest=candidate["candidate_digest"],
        verdict="accepted",
        evidence=_passing_evidence(),
    )

    assert accepted["status"] == "DONE"
    assert accepted["acceptance"]["reviewer_id"] == mission_runtime._LOCAL_ACCEPTANCE_REVIEWER_ID
    proof = accepted["acceptance"]["evidence"]
    assert proof["running_sha"] == "f" * 40
    assert proof["data_root"] == str(isolated_data.resolve())
    assert proof["candidate_ref"] == candidate_ref
    assert proof["candidate_digest"] == candidate["candidate_digest"]
    assert proof["artifact_provenance"]["review_sha"] == "d" * 40


def test_local_operator_rejects_stale_candidate_reference(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "kitty.db"
    monkeypatch.setattr(memory_mission, "MISSION_DB_FILE", db_path)
    _verifying_mission(db_path, mission_id="r3-stale")
    candidate = _candidate()
    memory_mission.record_candidate(
        "r3-stale",
        candidate_ref=f"artifact:{candidate['artifact_id']}",
        candidate_digest=candidate["candidate_digest"],
        db_path=db_path,
    )

    with pytest.raises(memory_mission.MissionError, match="stale candidate reference or digest"):
        mission_runtime.record_running_product_acceptance(
            "r3-stale",
            candidate_ref="artifact:older-attempt",
            candidate_digest=candidate["candidate_digest"],
            verdict="accepted",
            evidence=_passing_evidence(),
        )


def test_accepted_evidence_requires_every_running_gate_passed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "kitty.db"
    monkeypatch.setattr(memory_mission, "MISSION_DB_FILE", db_path)
    _verifying_mission(db_path, mission_id="r3-unmet")
    candidate = _candidate()
    candidate_ref = f"artifact:{candidate['artifact_id']}"
    memory_mission.record_candidate(
        "r3-unmet",
        candidate_ref=candidate_ref,
        candidate_digest=candidate["candidate_digest"],
        db_path=db_path,
    )
    monkeypatch.setattr(mission_runtime, "_reviewed_builder_result", lambda mission: candidate)
    evidence = _passing_evidence()
    evidence["reload"] = {"state": "failed", "evidence": "evidence://reload-failure"}
    evidence["unmet_gates"] = ["reload"]

    with pytest.raises(memory_mission.MissionError, match="cannot contain unmet gates"):
        mission_runtime.record_running_product_acceptance(
            "r3-unmet",
            candidate_ref=candidate_ref,
            candidate_digest=candidate["candidate_digest"],
            verdict="accepted",
            evidence=evidence,
        )


def test_reconcile_result_candidate_propagates_source_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "kitty.db"
    monkeypatch.setattr(memory_mission, "MISSION_DB_FILE", db_path)
    _verifying_mission(db_path, mission_id="r3-source-failure")

    def unavailable(_mission):
        raise mission_runtime.ResultCandidateUnavailable("artifact disappeared")

    monkeypatch.setattr(mission_runtime, "_reviewed_builder_result", unavailable)

    with pytest.raises(mission_runtime.ResultCandidateUnavailable, match="artifact disappeared"):
        mission_runtime.reconcile_result_candidate("r3-source-failure")
