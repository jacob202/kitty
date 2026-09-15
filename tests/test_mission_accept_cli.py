"""The local acceptance operator needs a way in; these prove it has one."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gateway import memory_mission, mission_accept_cli, mission_runtime


def _executing_mission(db_path: Path, mission_id: str = "accept-cli") -> None:
    memory_mission.create_mission(
        mission_id=mission_id,
        objective="Ask for one bounded result and get it back",
        definition_of_done=["The running journey is independently accepted."],
        supervisor_id="kitty",
        db_path=db_path,
    )
    memory_mission.bind_builder_locator(
        mission_id, initiative_id="builder-initiative-1", task_id="builder-task-1", db_path=db_path
    )
    memory_mission.set_plan(
        mission_id, plan_ref="docs/plan.md@" + "a" * 40, plan_digest="b" * 64, db_path=db_path
    )
    memory_mission.record_plan_review(
        mission_id,
        reviewer_id="independent-plan-reviewer",
        plan_digest="b" * 64,
        verdict="approved",
        db_path=db_path,
    )
    memory_mission.begin_execution(mission_id, db_path=db_path)


def _candidate() -> dict[str, str]:
    base = {
        "artifact_id": "builder_result_builder-task-1_attempt-7",
        "content_hash": "c" * 64,
        "base_sha": "a" * 40,
        "review_sha": "d" * 40,
        "diff_sha256": "e" * 64,
    }
    return {**base, "candidate_digest": mission_runtime._candidate_provenance_digest(base)}


def _passing_evidence() -> dict:
    evidence: dict = {"steps": ["asked", "approved", "got the result"], "unmet_gates": []}
    for key in mission_runtime.REQUIRED_RUNNING_STATES:
        evidence[key] = {"state": "passed", "evidence": f"evidence://{key}"}
    return evidence


@pytest.fixture()
def mission_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    db_path = tmp_path / "kitty.db"
    monkeypatch.setattr(memory_mission, "MISSION_DB_FILE", db_path)
    return db_path


def test_status_names_the_exact_blocker_rather_than_saying_not_ready(
    mission_db: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _executing_mission(mission_db)

    def unavailable(_mission):
        raise mission_runtime.ResultCandidateUnavailable("bound Builder task is unavailable")

    monkeypatch.setattr(mission_runtime, "_reviewed_builder_result", unavailable)
    candidate = _candidate()
    memory_mission.record_candidate(
        "accept-cli",
        candidate_ref=f"artifact:{candidate['artifact_id']}",
        candidate_digest=candidate["candidate_digest"],
        db_path=mission_db,
    )

    assert mission_accept_cli.main(["status", "--json"]) == 0

    report = json.loads(capsys.readouterr().out)["awaiting_acceptance"][0]
    assert report["mission_id"] == "accept-cli"
    assert report["ready"] is False
    assert report["blocker"] == "bound Builder task is unavailable"


def test_a_fixable_blocker_prints_the_command_that_clears_it(
    mission_db: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A blocker with no command next to it is a task handed back to Jacob."""
    _executing_mission(mission_db)
    candidate = _candidate()
    memory_mission.record_candidate(
        "accept-cli",
        candidate_ref=f"artifact:{candidate['artifact_id']}",
        candidate_digest=candidate["candidate_digest"],
        db_path=mission_db,
    )
    monkeypatch.setattr(mission_runtime, "_reviewed_builder_result", lambda mission: candidate)

    def not_running(_sha):
        raise mission_runtime.ResultCandidateUnavailable(
            "Gateway runtime identity is unavailable: stopped"
        )

    monkeypatch.setattr(mission_runtime, "_running_product_runtime_identity", not_running)

    assert mission_accept_cli.main(["status"]) == 0

    out = capsys.readouterr().out
    assert "Kitty's server is not running." in out
    assert "./kitty up" in out
    assert "Gateway runtime identity is unavailable: stopped" in out


def test_status_reports_ready_when_the_running_product_matches(
    mission_db: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _executing_mission(mission_db)
    candidate = _candidate()
    memory_mission.record_candidate(
        "accept-cli",
        candidate_ref=f"artifact:{candidate['artifact_id']}",
        candidate_digest=candidate["candidate_digest"],
        db_path=mission_db,
    )
    monkeypatch.setattr(mission_runtime, "_reviewed_builder_result", lambda mission: candidate)
    monkeypatch.setattr(
        mission_runtime, "_running_product_runtime_identity", lambda sha: {"data_root": "/tmp"}
    )

    assert mission_accept_cli.main(["status", "--json"]) == 0

    report = json.loads(capsys.readouterr().out)["awaiting_acceptance"][0]
    assert report["ready"] is True
    assert report["review_sha"] == "d" * 40
    assert report["blocker"] is None


def test_status_refuses_stale_bound_candidate_digest(
    mission_db: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _executing_mission(mission_db)
    candidate = _candidate()
    memory_mission.record_candidate(
        "accept-cli",
        candidate_ref=f"artifact:{candidate['artifact_id']}",
        candidate_digest="f" * 64,
        db_path=mission_db,
    )
    monkeypatch.setattr(mission_runtime, "_reviewed_builder_result", lambda mission: candidate)
    monkeypatch.setattr(
        mission_runtime, "_running_product_runtime_identity", lambda sha: {"data_root": "/tmp"}
    )

    assert mission_accept_cli.main(["status", "--json"]) == 0

    report = json.loads(capsys.readouterr().out)["awaiting_acceptance"][0]
    assert report["ready"] is False
    assert report["blocker"] == "the bound candidate does not match the reviewed Builder result"


def test_status_surfaces_persisted_candidate_reconciliation_failure(
    mission_db: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _executing_mission(mission_db)
    memory_mission.record_candidate_unavailable(
        "accept-cli", reason="Builder result artifact cannot be read: missing", db_path=mission_db
    )

    assert mission_accept_cli.main(["status", "--json"]) == 0

    report = json.loads(capsys.readouterr().out)["awaiting_acceptance"][0]
    assert report["ready"] is False
    assert report["blocker"] == "Builder result artifact cannot be read: missing"


def test_template_lists_every_gate_the_operator_must_answer(
    mission_db: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _executing_mission(mission_db)
    out = tmp_path / "evidence.json"

    assert mission_accept_cli.main(["template", "accept-cli", "-o", str(out)]) == 0

    payload = json.loads(out.read_text(encoding="utf-8"))
    for key in mission_runtime.REQUIRED_RUNNING_STATES:
        assert payload[key]["state"] == "unverified"
    assert payload["unmet_gates"] == []
    assert "kitty accept record" in capsys.readouterr().out


def test_record_accepts_against_the_missions_own_bound_candidate(
    mission_db: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _executing_mission(mission_db)
    candidate = _candidate()
    memory_mission.record_candidate(
        "accept-cli",
        candidate_ref=f"artifact:{candidate['artifact_id']}",
        candidate_digest=candidate["candidate_digest"],
        db_path=mission_db,
    )
    monkeypatch.setattr(mission_runtime, "_reviewed_builder_result", lambda mission: candidate)
    monkeypatch.setattr(
        mission_runtime,
        "_running_product_runtime_identity",
        lambda sha: {"gateway": {"commit": sha}, "ui": {"commit": sha}, "data_root": "/tmp/data"},
    )
    evidence_file = tmp_path / "evidence.json"
    # An evidence file stamped for a superseded candidate is refused outright.
    # Silently re-pointing it at the live binding would accept a candidate the
    # operator never actually exercised.
    evidence_file.write_text(
        json.dumps({**_passing_evidence(), "candidate_digest": "0" * 64}), encoding="utf-8"
    )

    assert mission_accept_cli.main(["record", "accept-cli", "-e", str(evidence_file)]) == 1

    mission = memory_mission.get_mission("accept-cli", db_path=mission_db)
    assert mission["status"] == "VERIFYING"
    assert mission["acceptance"]["state"] == "unreviewed"

    # The Mission's own binding remains the authority for a current file: the
    # operator never supplies the digest that is recorded.
    evidence_file.write_text(json.dumps(_passing_evidence()), encoding="utf-8")

    assert mission_accept_cli.main(["record", "accept-cli", "-e", str(evidence_file)]) == 0

    mission = memory_mission.get_mission("accept-cli", db_path=mission_db)
    assert mission["status"] == "DONE"
    assert mission["acceptance"]["reviewer_id"] == mission_runtime._LOCAL_ACCEPTANCE_REVIEWER_ID
    assert mission["acceptance"]["evidence"]["candidate_digest"] == candidate["candidate_digest"]


def test_record_refuses_an_evidence_file_stamped_for_another_job(
    mission_db: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A template generated for a different Mission must never be submitted here."""
    _executing_mission(mission_db)
    candidate = _candidate()
    memory_mission.record_candidate(
        "accept-cli",
        candidate_ref=f"artifact:{candidate['artifact_id']}",
        candidate_digest=candidate["candidate_digest"],
        db_path=mission_db,
    )
    monkeypatch.setattr(mission_runtime, "_reviewed_builder_result", lambda mission: candidate)
    evidence_file = tmp_path / "evidence.json"
    evidence_file.write_text(
        json.dumps({**_passing_evidence(), "mission_id": "some-other-job"}), encoding="utf-8"
    )

    assert mission_accept_cli.main(["record", "accept-cli", "-e", str(evidence_file)]) == 1

    err = capsys.readouterr().err
    assert "some-other-job" in err
    assert memory_mission.get_mission("accept-cli", db_path=mission_db)["status"] == "VERIFYING"


def test_record_refuses_when_the_running_product_is_not_the_reviewed_one(
    mission_db: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _executing_mission(mission_db)
    candidate = _candidate()
    memory_mission.record_candidate(
        "accept-cli",
        candidate_ref=f"artifact:{candidate['artifact_id']}",
        candidate_digest=candidate["candidate_digest"],
        db_path=mission_db,
    )
    monkeypatch.setattr(mission_runtime, "_reviewed_builder_result", lambda mission: candidate)

    def wrong_runtime(_sha):
        raise mission_runtime.ResultCandidateUnavailable("Gateway is serving 'eee', expected reviewed SHA ddd")

    monkeypatch.setattr(mission_runtime, "_running_product_runtime_identity", wrong_runtime)
    evidence_file = tmp_path / "evidence.json"
    evidence_file.write_text(json.dumps(_passing_evidence()), encoding="utf-8")

    assert mission_accept_cli.main(["record", "accept-cli", "-e", str(evidence_file)]) == 1

    assert "expected reviewed SHA" in capsys.readouterr().err
    assert memory_mission.get_mission("accept-cli", db_path=mission_db)["status"] != "DONE"
