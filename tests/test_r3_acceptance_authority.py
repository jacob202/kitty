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


def _candidate(*, base_sha: str = "a" * 40, review_sha: str = "d" * 40) -> dict[str, str]:
    base = {
        "artifact_id": "builder_result_builder-task-1_attempt-7",
        "content_hash": "c" * 64,
        "base_sha": base_sha,
        "review_sha": review_sha,
        "diff_sha256": "e" * 64,
    }
    return {**base, "candidate_digest": mission_runtime._candidate_provenance_digest(base)}


def _passing_evidence() -> dict:
    evidence = {
        "steps": ["Chat request", "Mission approval", "Builder result", "Library reuse", "Chat reuse"],
        "unmet_gates": [],
    }
    for key in mission_runtime.REQUIRED_RUNNING_STATES:
        evidence[key] = {"state": "passed", "evidence": f"evidence://{key}"}
    return evidence


def test_candidate_digest_changes_when_review_revision_changes() -> None:
    first = _candidate(base_sha="a" * 40, review_sha="d" * 40)
    rereviewed = _candidate(base_sha="a" * 40, review_sha="f" * 40)
    rebased = _candidate(base_sha="b" * 40, review_sha="d" * 40)

    assert first["content_hash"] == rereviewed["content_hash"] == rebased["content_hash"]
    assert first["candidate_digest"] != rereviewed["candidate_digest"]
    assert first["candidate_digest"] != rebased["candidate_digest"]


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
    isolated_data = tmp_path / "isolated-data"
    runtime_identity = {
        "gateway": {
            "pid": 101,
            "cwd": str(tmp_path),
            "root": str(tmp_path),
            "commit": "d" * 40,
            "manifest_revision": "runtime-proof",
        },
        "ui": {
            "pid": "202",
            "root": str(tmp_path),
            "build_id": "ui-proof",
            "commit": "d" * 40,
        },
        "data_root": str(isolated_data.resolve()),
    }
    seen_review_shas: list[str] = []

    def runtime_probe(expected_review_sha: str) -> dict:
        seen_review_shas.append(expected_review_sha)
        return runtime_identity

    monkeypatch.setattr(
        mission_runtime,
        "_running_product_runtime_identity",
        runtime_probe,
    )

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
    assert seen_review_shas == ["d" * 40]
    assert proof["data_root"] == str(isolated_data.resolve())
    assert proof["running_sha"] == "d" * 40
    assert proof["runtime_identity"] == runtime_identity
    assert proof["candidate_ref"] == candidate_ref
    assert proof["candidate_digest"] == candidate["candidate_digest"]
    assert proof["artifact_provenance"]["base_sha"] == "a" * 40
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


def test_background_reconciliation_keeps_the_reason_it_could_not_bind(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "kitty.db"
    monkeypatch.setattr(memory_mission, "MISSION_DB_FILE", db_path)
    _verifying_mission(db_path, mission_id="r3-background-failure")

    def unavailable(_mission):
        raise mission_runtime.ResultCandidateUnavailable("artifact disappeared")

    monkeypatch.setattr(mission_runtime, "_reviewed_builder_result", unavailable)

    receipt = mission_runtime.reconcile_result_candidate_background("r3-background-failure")

    assert receipt["status"] == "source_unavailable"
    assert receipt["error"] == "artifact disappeared"
    mission = memory_mission.get_mission("r3-background-failure", db_path=db_path)
    assert mission["candidate"]["error"] == "artifact disappeared"
    assert mission["status"] == "EXECUTING"


def test_a_later_successful_bind_clears_the_recorded_reason(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "kitty.db"
    monkeypatch.setattr(memory_mission, "MISSION_DB_FILE", db_path)
    _verifying_mission(db_path, mission_id="r3-recovered")
    memory_mission.record_candidate_unavailable(
        "r3-recovered", reason="Builder result store is unavailable", db_path=db_path
    )
    candidate = _candidate()
    monkeypatch.setattr(mission_runtime, "_reviewed_builder_result", lambda mission: candidate)

    receipt = mission_runtime.reconcile_result_candidate_background("r3-recovered")

    assert receipt["status"] == "candidate_bound"
    assert memory_mission.get_mission("r3-recovered", db_path=db_path)["candidate"]["error"] is None


def _runtime_manifest(root: Path, data_root: Path, sha: str) -> dict:
    return {
        "revision": "runtime-proof",
        "context": {
            "repository": {
                "state": "available",
                "value": {
                    "root": str(root),
                    "branch": "acceptance",
                    "commit": sha,
                    "dirty": False,
                    "changed_paths": 0,
                },
            }
        },
        "storage": {
            "data_root": {
                "state": "available",
                "value": str(data_root),
            }
        },
    }


def _ui_runtime(root: Path, sha: str) -> dict[str, str]:
    return {
        "state": "checkout-current",
        "build_id": "ui-build-proof",
        "build_source": sha,
        "source_sha": sha,
        "source_state": "clean",
        "runtime_root": str(root),
        "runtime_pid": "202",
    }


def test_runtime_identity_binds_actual_gateway_and_ui_to_reviewed_sha(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "candidate"
    root.mkdir()
    data_root = tmp_path / "isolated-data"
    sha = "d" * 40
    monkeypatch.setattr(mission_runtime, "DATA_DIR", data_root)
    monkeypatch.setattr(
        mission_runtime.doctor,
        "_gateway_process_info",
        lambda **kwargs: {"state": "running", "pid": 101, "cwd": str(root)},
    )
    monkeypatch.setattr(
        mission_runtime,
        "_gateway_runtime_manifest",
        lambda **kwargs: _runtime_manifest(root, data_root, sha),
    )
    monkeypatch.setattr(
        mission_runtime.doctor,
        "_ui_runtime_provenance",
        lambda **kwargs: _ui_runtime(root, sha),
    )

    identity = mission_runtime._running_product_runtime_identity(sha)

    assert identity["gateway"]["commit"] == sha
    assert identity["ui"]["commit"] == sha
    assert identity["gateway"]["root"] == identity["ui"]["root"] == str(root.resolve())
    assert identity["data_root"] == str(data_root.resolve())


def test_runtime_identity_rejects_gateway_at_other_sha(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "candidate"
    root.mkdir()
    data_root = tmp_path / "isolated-data"
    monkeypatch.setattr(mission_runtime, "DATA_DIR", data_root)
    monkeypatch.setattr(
        mission_runtime.doctor,
        "_gateway_process_info",
        lambda **kwargs: {"state": "running", "pid": 101, "cwd": str(root)},
    )
    monkeypatch.setattr(
        mission_runtime,
        "_gateway_runtime_manifest",
        lambda **kwargs: _runtime_manifest(root, data_root, "e" * 40),
    )

    with pytest.raises(mission_runtime.ResultCandidateUnavailable, match="expected reviewed SHA"):
        mission_runtime._running_product_runtime_identity("d" * 40)


def test_runtime_identity_rejects_ui_at_other_sha(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "candidate"
    root.mkdir()
    data_root = tmp_path / "isolated-data"
    sha = "d" * 40
    monkeypatch.setattr(mission_runtime, "DATA_DIR", data_root)
    monkeypatch.setattr(
        mission_runtime.doctor,
        "_gateway_process_info",
        lambda **kwargs: {"state": "running", "pid": 101, "cwd": str(root)},
    )
    monkeypatch.setattr(
        mission_runtime,
        "_gateway_runtime_manifest",
        lambda **kwargs: _runtime_manifest(root, data_root, sha),
    )
    monkeypatch.setattr(
        mission_runtime.doctor,
        "_ui_runtime_provenance",
        lambda **kwargs: _ui_runtime(root, "e" * 40),
    )

    with pytest.raises(mission_runtime.ResultCandidateUnavailable, match="UI is not serving"):
        mission_runtime._running_product_runtime_identity(sha)


def test_runtime_identity_rejects_other_gateway_data_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "candidate"
    root.mkdir()
    expected_data = tmp_path / "expected-data"
    actual_data = tmp_path / "other-data"
    sha = "d" * 40
    monkeypatch.setattr(mission_runtime, "DATA_DIR", expected_data)
    monkeypatch.setattr(
        mission_runtime.doctor,
        "_gateway_process_info",
        lambda **kwargs: {"state": "running", "pid": 101, "cwd": str(root)},
    )
    monkeypatch.setattr(
        mission_runtime,
        "_gateway_runtime_manifest",
        lambda **kwargs: _runtime_manifest(root, actual_data, sha),
    )

    with pytest.raises(mission_runtime.ResultCandidateUnavailable, match="does not match operator data root"):
        mission_runtime._running_product_runtime_identity(sha)
