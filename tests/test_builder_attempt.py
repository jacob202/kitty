"""Tests for gateway/builder_attempt.py — KB-S2 attempts and contracts.

Covers: implementation/review contract validation with size caps, attempt
lifecycle (start/limit/one-open/record/close), bounded context bundles that
preserve prior-attempt digests, and the CLI surface.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gateway import builder_attempt as ba
from gateway import builder_initiative as bi
from gateway import builder_queue as bq
from gateway.builder_cli import main

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

INITIATIVE = "kitty-alpha-v1"
PACKET = "KB-A1"


def _manifest() -> dict:
    return {
        "manifest_version": 1,
        "initiative_id": INITIATIVE,
        "title": "Kitty Alpha build",
        "packets": [
            {
                "id": PACKET,
                "title": "First packet",
                "objective": "Do the first thing.",
                "acceptance_criteria": ["it works"],
                "allowed_paths": ["gateway/a.py"],
                "policy": {"max_attempts": 2},
            },
            {
                "id": "KB-A2",
                "title": "Second packet",
                "objective": "Do the second thing.",
                "depends_on": [PACKET],
                "acceptance_criteria": ["it also works"],
                "allowed_paths": ["gateway/b.py"],
            },
        ],
    }


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    p = tmp_path / "kittybuilder" / "builder_queue.db"
    ba.init_db(p)
    bi.apply_manifest(_manifest(), db_path=p)
    return p


def _impl(**overrides) -> dict:
    base = {
        "contract_version": 1,
        "status": "completed",
        "summary": "Implemented the thing.",
        "validation": {"passed": True, "output": "5 passed"},
    }
    base.update(overrides)
    return base


def _review(**overrides) -> dict:
    base = {
        "contract_version": 1,
        "verdict": "approve",
        "summary": "Looks correct.",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Contract validation
# ---------------------------------------------------------------------------


class TestImplementationContract:
    def test_valid(self):
        assert ba.validate_implementation_result(_impl()) == []

    def test_non_dict(self):
        assert ba.validate_implementation_result("done") == [
            "implementation result must be a JSON object"
        ]

    def test_wrong_version_and_status(self):
        errors = ba.validate_implementation_result(
            _impl(contract_version=9, status="shipped")
        )
        assert any("contract_version" in e for e in errors)
        assert any("status" in e for e in errors)

    def test_missing_summary(self):
        impl = _impl()
        del impl["summary"]
        assert any("summary" in e for e in ba.validate_implementation_result(impl))

    def test_summary_size_cap(self):
        errors = ba.validate_implementation_result(
            _impl(summary="x" * (ba.SUMMARY_CAP + 1))
        )
        assert any("exceeds" in e for e in errors)

    def test_validation_output_cap_and_shape(self):
        errors = ba.validate_implementation_result(
            _impl(validation={"passed": "yes", "output": "x" * (ba.OUTPUT_CAP + 1)})
        )
        assert any("passed" in e for e in errors)
        assert any("exceeds" in e for e in errors)

    def test_unknown_keys_rejected(self):
        errors = ba.validate_implementation_result(_impl(extra="nope"))
        assert any("unknown keys" in e for e in errors)

    def test_too_many_claims(self):
        errors = ba.validate_implementation_result(
            _impl(claims=["c"] * (ba.MAX_CLAIMS + 1))
        )
        assert any("claims" in e for e in errors)


class TestReviewContract:
    def test_valid(self):
        assert ba.validate_review_result(_review()) == []

    def test_bad_verdict(self):
        errors = ba.validate_review_result(_review(verdict="lgtm"))
        assert any("verdict" in e for e in errors)

    def test_findings_validated(self):
        errors = ba.validate_review_result(
            _review(findings=[{"severity": "huge", "note": ""}])
        )
        assert any("severity" in e for e in errors)
        assert any("note" in e for e in errors)

    def test_too_many_findings(self):
        errors = ba.validate_review_result(
            _review(
                findings=[{"severity": "minor", "note": "n"}] * (ba.MAX_FINDINGS + 1)
            )
        )
        assert any("findings" in e for e in errors)


# ---------------------------------------------------------------------------
# Attempt lifecycle
# ---------------------------------------------------------------------------


class TestAttemptLifecycle:
    def test_start_creates_attempt_one_with_bundle(self, db_path: Path):
        attempt = ba.start_attempt(INITIATIVE, PACKET, db_path=db_path)
        assert attempt["attempt_no"] == 1
        assert attempt["outcome"] is None
        bundle = attempt["bundle"]
        assert bundle["bundle_version"] == 1
        assert bundle["objective"] == "Do the first thing."
        assert bundle["acceptance_criteria"] == ["it works"]
        assert bundle["allowed_paths"] == ["gateway/a.py"]
        assert bundle["prior_attempts"] == []
        assert bundle["task_id"] == attempt["task_id"]

    def test_unknown_packet_rejected(self, db_path: Path):
        with pytest.raises(ba.AttemptError, match="unknown packet"):
            ba.start_attempt(INITIATIVE, "KB-GONE", db_path=db_path)

    def test_one_open_attempt_at_a_time(self, db_path: Path):
        ba.start_attempt(INITIATIVE, PACKET, db_path=db_path)
        with pytest.raises(ba.AttemptStateError, match="still open"):
            ba.start_attempt(INITIATIVE, PACKET, db_path=db_path)

    def test_max_attempts_enforced(self, db_path: Path):
        for _ in range(2):  # policy.max_attempts = 2
            attempt = ba.start_attempt(INITIATIVE, PACKET, db_path=db_path)
            ba.close_attempt(attempt["id"], "failed", db_path=db_path)
        with pytest.raises(ba.AttemptLimitError, match="2/2"):
            ba.start_attempt(INITIATIVE, PACKET, db_path=db_path)

    def test_default_max_attempts_when_no_policy(self, db_path: Path):
        for _ in range(ba.DEFAULT_MAX_ATTEMPTS):
            attempt = ba.start_attempt(INITIATIVE, "KB-A2", db_path=db_path)
            ba.close_attempt(attempt["id"], "failed", db_path=db_path)
        with pytest.raises(ba.AttemptLimitError):
            ba.start_attempt(INITIATIVE, "KB-A2", db_path=db_path)

    def test_record_implementation_then_review(self, db_path: Path):
        attempt = ba.start_attempt(INITIATIVE, PACKET, db_path=db_path)
        updated = ba.record_implementation_result(
            attempt["id"], _impl(), db_path=db_path
        )
        assert updated["implementation"]["status"] == "completed"
        updated = ba.record_review_result(attempt["id"], _review(), db_path=db_path)
        assert updated["review"]["verdict"] == "approve"

    def test_review_requires_implementation(self, db_path: Path):
        attempt = ba.start_attempt(INITIATIVE, PACKET, db_path=db_path)
        with pytest.raises(ba.AttemptStateError, match="no implementation"):
            ba.record_review_result(attempt["id"], _review(), db_path=db_path)

    def test_results_are_write_once(self, db_path: Path):
        attempt = ba.start_attempt(INITIATIVE, PACKET, db_path=db_path)
        ba.record_implementation_result(attempt["id"], _impl(), db_path=db_path)
        with pytest.raises(ba.AttemptStateError, match="already has"):
            ba.record_implementation_result(attempt["id"], _impl(), db_path=db_path)

    def test_invalid_result_rejected_and_not_stored(self, db_path: Path):
        attempt = ba.start_attempt(INITIATIVE, PACKET, db_path=db_path)
        with pytest.raises(ba.ResultContractError):
            ba.record_implementation_result(
                attempt["id"], _impl(status="shipped"), db_path=db_path
            )
        assert ba.get_attempt(attempt["id"], db_path=db_path)["implementation"] is None

    def test_close_requires_valid_outcome(self, db_path: Path):
        attempt = ba.start_attempt(INITIATIVE, PACKET, db_path=db_path)
        with pytest.raises(ba.AttemptError, match="outcome"):
            ba.close_attempt(attempt["id"], "done", db_path=db_path)

    def test_closed_attempt_rejects_mutation(self, db_path: Path):
        attempt = ba.start_attempt(INITIATIVE, PACKET, db_path=db_path)
        ba.close_attempt(attempt["id"], "aborted", db_path=db_path)
        with pytest.raises(ba.AttemptStateError, match="closed"):
            ba.record_implementation_result(attempt["id"], _impl(), db_path=db_path)
        with pytest.raises(ba.AttemptStateError, match="closed"):
            ba.close_attempt(attempt["id"], "failed", db_path=db_path)

    def test_missing_attempt_raises_not_found(self, db_path: Path):
        with pytest.raises(ba.AttemptNotFoundError):
            ba.close_attempt(999, "failed", db_path=db_path)

    def test_events_appended_to_task(self, db_path: Path):
        attempt = ba.start_attempt(INITIATIVE, PACKET, db_path=db_path)
        ba.record_implementation_result(attempt["id"], _impl(), db_path=db_path)
        ba.record_review_result(attempt["id"], _review(), db_path=db_path)
        ba.close_attempt(attempt["id"], "succeeded", db_path=db_path)
        events = [
            e["type"]
            for e in bq.list_events(attempt["task_id"], db_path=db_path)
        ]
        for expected in (
            "attempt_started",
            "attempt_implementation_recorded",
            "attempt_review_recorded",
            "attempt_closed",
        ):
            assert expected in events

    def test_task_state_machine_untouched(self, db_path: Path):
        """Attempt lifecycle never mutates the queue task's state."""
        attempt = ba.start_attempt(INITIATIVE, PACKET, db_path=db_path)
        ba.record_implementation_result(attempt["id"], _impl(), db_path=db_path)
        ba.close_attempt(attempt["id"], "failed", db_path=db_path)
        task = bq.get_task(attempt["task_id"], db_path=db_path)
        assert task["state"] == bq.QUEUED


# ---------------------------------------------------------------------------
# Context bundle across attempts
# ---------------------------------------------------------------------------


class TestContextBundle:
    def test_second_attempt_sees_first_attempt_digest(self, db_path: Path):
        first = ba.start_attempt(INITIATIVE, PACKET, db_path=db_path)
        ba.record_implementation_result(
            first["id"], _impl(status="failed", summary="Broke a test."),
            db_path=db_path,
        )
        ba.record_review_result(
            first["id"],
            _review(verdict="request_changes", summary="Fix the test."),
            db_path=db_path,
        )
        ba.close_attempt(first["id"], "failed", db_path=db_path)

        second = ba.start_attempt(INITIATIVE, PACKET, db_path=db_path)
        priors = second["bundle"]["prior_attempts"]
        assert len(priors) == 1
        assert priors[0]["attempt_no"] == 1
        assert priors[0]["outcome"] == "failed"
        assert priors[0]["implementation"]["summary"] == "Broke a test."
        assert priors[0]["review"]["verdict"] == "request_changes"

    def test_prior_summaries_are_clipped(self, db_path: Path):
        first = ba.start_attempt(INITIATIVE, PACKET, db_path=db_path)
        ba.record_implementation_result(
            first["id"], _impl(summary="y" * ba.SUMMARY_CAP), db_path=db_path
        )
        ba.close_attempt(first["id"], "failed", db_path=db_path)

        second = ba.start_attempt(INITIATIVE, PACKET, db_path=db_path)
        clipped = second["bundle"]["prior_attempts"][0]["implementation"]["summary"]
        assert len(clipped) <= ba.NOTE_CAP
        assert clipped.endswith("…[clipped]")

    def test_bundle_preview_is_read_only(self, db_path: Path):
        bundle = ba.build_context_bundle(INITIATIVE, PACKET, db_path=db_path)
        assert bundle["attempt_no"] == 1
        assert ba.list_attempts(INITIATIVE, db_path=db_path) == []

    def test_prior_window_is_bounded(self, db_path: Path):
        # Allow enough attempts to exceed the window.
        manifest = _manifest()
        manifest["initiative_id"] = "window-test"
        manifest["packets"][0]["policy"] = {"max_attempts": 5}
        bi.apply_manifest(manifest, db_path=db_path)
        for i in range(5):
            attempt = ba.start_attempt("window-test", PACKET, db_path=db_path)
            ba.close_attempt(attempt["id"], "failed", db_path=db_path)
        bundle = ba.build_context_bundle("window-test", PACKET, db_path=db_path)
        priors = bundle["prior_attempts"]
        assert len(priors) == ba.PRIOR_ATTEMPT_WINDOW
        # Most recent attempts, oldest first.
        assert [p["attempt_no"] for p in priors] == [3, 4, 5]


# ---------------------------------------------------------------------------
# Deterministic validation (KB-S3a)
# ---------------------------------------------------------------------------


def _apply_with_commands(db_path: Path, commands: list[str]) -> None:
    manifest = _manifest()
    manifest["initiative_id"] = "val-test"
    manifest["packets"][0]["validation_commands"] = commands
    bi.apply_manifest(manifest, db_path=db_path)


class TestRunValidation:
    def test_all_commands_pass(self, db_path: Path, tmp_path: Path):
        _apply_with_commands(db_path, ["true", "echo hello"])
        attempt = ba.start_attempt("val-test", PACKET, db_path=db_path)
        assert attempt["bundle"]["validation_commands"] == ["true", "echo hello"]
        updated = ba.run_validation(attempt["id"], cwd=tmp_path, db_path=db_path)
        validation = updated["validation"]
        assert validation["status"] == "passed"
        assert [r["passed"] for r in validation["commands"]] == [True, True]
        assert "hello" in validation["commands"][1]["output_tail"]

    def test_failing_command_fails_validation(self, db_path: Path, tmp_path: Path):
        _apply_with_commands(db_path, ["true", "false"])
        attempt = ba.start_attempt("val-test", PACKET, db_path=db_path)
        updated = ba.run_validation(attempt["id"], cwd=tmp_path, db_path=db_path)
        assert updated["validation"]["status"] == "failed"
        assert updated["validation"]["commands"][1]["exit_code"] == 1

    def test_no_commands_is_skipped(self, db_path: Path, tmp_path: Path):
        attempt = ba.start_attempt(INITIATIVE, PACKET, db_path=db_path)
        updated = ba.run_validation(attempt["id"], cwd=tmp_path, db_path=db_path)
        assert updated["validation"] == {"status": "skipped", "commands": []}

    def test_runs_in_given_cwd(self, db_path: Path, tmp_path: Path):
        (tmp_path / "marker.txt").write_text("here", encoding="utf-8")
        _apply_with_commands(db_path, ["cat marker.txt"])
        attempt = ba.start_attempt("val-test", PACKET, db_path=db_path)
        updated = ba.run_validation(attempt["id"], cwd=tmp_path, db_path=db_path)
        assert updated["validation"]["status"] == "passed"
        assert "here" in updated["validation"]["commands"][0]["output_tail"]

    def test_missing_cwd_fails_loud(self, db_path: Path, tmp_path: Path):
        _apply_with_commands(db_path, ["true"])
        attempt = ba.start_attempt("val-test", PACKET, db_path=db_path)
        with pytest.raises(ba.AttemptError, match="does not exist"):
            ba.run_validation(
                attempt["id"], cwd=tmp_path / "nope", db_path=db_path
            )

    def test_timeout_records_failure(self, db_path: Path, tmp_path: Path):
        _apply_with_commands(db_path, ["sleep 5"])
        attempt = ba.start_attempt("val-test", PACKET, db_path=db_path)
        updated = ba.run_validation(
            attempt["id"], cwd=tmp_path, timeout_seconds=1, db_path=db_path
        )
        record = updated["validation"]["commands"][0]
        assert updated["validation"]["status"] == "failed"
        assert record["exit_code"] is None
        assert "TIMEOUT" in record["output_tail"]

    def test_validation_is_write_once(self, db_path: Path, tmp_path: Path):
        attempt = ba.start_attempt(INITIATIVE, PACKET, db_path=db_path)
        ba.run_validation(attempt["id"], cwd=tmp_path, db_path=db_path)
        with pytest.raises(ba.AttemptStateError, match="already has"):
            ba.run_validation(attempt["id"], cwd=tmp_path, db_path=db_path)

    def test_closed_attempt_rejected(self, db_path: Path, tmp_path: Path):
        attempt = ba.start_attempt(INITIATIVE, PACKET, db_path=db_path)
        ba.close_attempt(attempt["id"], "aborted", db_path=db_path)
        with pytest.raises(ba.AttemptStateError, match="closed"):
            ba.run_validation(attempt["id"], cwd=tmp_path, db_path=db_path)

    def test_output_tail_is_capped(self, db_path: Path, tmp_path: Path):
        _apply_with_commands(
            db_path, ["python3 -c \"print('x' * 20000)\""]
        )
        attempt = ba.start_attempt("val-test", PACKET, db_path=db_path)
        updated = ba.run_validation(attempt["id"], cwd=tmp_path, db_path=db_path)
        assert len(updated["validation"]["commands"][0]["output_tail"]) <= ba.OUTPUT_CAP

    def test_event_appended(self, db_path: Path, tmp_path: Path):
        attempt = ba.start_attempt(INITIATIVE, PACKET, db_path=db_path)
        ba.run_validation(attempt["id"], cwd=tmp_path, db_path=db_path)
        events = [
            e["type"] for e in bq.list_events(attempt["task_id"], db_path=db_path)
        ]
        assert "attempt_validation_recorded" in events

    def test_manifest_rejects_bad_validation_commands(self):
        manifest = _manifest()
        manifest["packets"][0]["validation_commands"] = ["", 3]
        errors = bi.validate_manifest(manifest)
        assert any("validation_commands" in e for e in errors)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


@pytest.fixture
def cli_db(tmp_path: Path, monkeypatch) -> Path:
    p = tmp_path / "kittybuilder" / "builder_queue.db"
    monkeypatch.setattr(bq, "BUILDER_QUEUE_DB", p)
    ba.init_db(p)
    bi.apply_manifest(_manifest(), db_path=p)
    return p


class TestCli:
    def test_start_record_close_roundtrip(self, tmp_path: Path, cli_db, capsys):
        assert main(["initiative", "start-attempt", INITIATIVE, PACKET, "--json"]) == 0
        attempt = json.loads(capsys.readouterr().out)

        impl_file = tmp_path / "impl.json"
        impl_file.write_text(json.dumps(_impl()), encoding="utf-8")
        assert main(
            ["initiative", "record-implementation", str(attempt["id"]),
             "--file", str(impl_file)]
        ) == 0
        capsys.readouterr()

        review_file = tmp_path / "review.json"
        review_file.write_text(json.dumps(_review()), encoding="utf-8")
        assert main(
            ["initiative", "record-review", str(attempt["id"]),
             "--file", str(review_file)]
        ) == 0
        capsys.readouterr()

        assert main(
            ["initiative", "close-attempt", str(attempt["id"]), "succeeded"]
        ) == 0
        assert "closed: succeeded" in capsys.readouterr().out

        assert main(["initiative", "attempts", INITIATIVE, "--json"]) == 0
        attempts = json.loads(capsys.readouterr().out)
        assert len(attempts) == 1
        assert attempts[0]["outcome"] == "succeeded"

    def test_record_invalid_contract_reports_errors(
        self, tmp_path: Path, cli_db, capsys
    ):
        assert main(["initiative", "start-attempt", INITIATIVE, PACKET, "--json"]) == 0
        attempt = json.loads(capsys.readouterr().out)
        bad = tmp_path / "bad.json"
        bad.write_text(json.dumps(_impl(status="shipped")), encoding="utf-8")
        assert main(
            ["initiative", "record-implementation", str(attempt["id"]),
             "--file", str(bad)]
        ) == 1
        assert "status" in capsys.readouterr().err

    def test_attempt_limit_surfaces_error(self, cli_db, capsys):
        for _ in range(2):
            assert main(
                ["initiative", "start-attempt", INITIATIVE, PACKET, "--json"]
            ) == 0
            attempt = json.loads(capsys.readouterr().out)
            main(["initiative", "close-attempt", str(attempt["id"]), "failed"])
            capsys.readouterr()
        assert main(["initiative", "start-attempt", INITIATIVE, PACKET]) == 1
        assert "2/2" in capsys.readouterr().err

    def test_kill_switch_blocks_attempt_mutations(self, cli_db, capsys, monkeypatch):
        monkeypatch.setenv("KITTY_BUILDER_QUEUE_ENABLED", "0")
        assert main(["initiative", "start-attempt", INITIATIVE, PACKET]) == 1
        assert "disabled" in capsys.readouterr().err
        # Reads still work.
        assert main(["initiative", "attempts", INITIATIVE]) == 0

    def test_attempts_filter_by_packet(self, cli_db, capsys):
        main(["initiative", "start-attempt", INITIATIVE, PACKET, "--json"])
        capsys.readouterr()
        assert main(["initiative", "attempts", INITIATIVE, "KB-A2", "--json"]) == 0
        assert json.loads(capsys.readouterr().out) == []

    def test_run_validation_cli(self, tmp_path: Path, cli_db, capsys):
        manifest = _manifest()
        manifest["initiative_id"] = "val-cli"
        manifest["packets"][0]["validation_commands"] = ["true"]
        bi.apply_manifest(manifest)
        assert main(["initiative", "start-attempt", "val-cli", PACKET, "--json"]) == 0
        attempt = json.loads(capsys.readouterr().out)
        assert main(
            ["initiative", "run-validation", str(attempt["id"]),
             "--cwd", str(tmp_path)]
        ) == 0
        assert "validation passed" in capsys.readouterr().out

    def test_run_validation_cli_failure_exit_code(
        self, tmp_path: Path, cli_db, capsys
    ):
        manifest = _manifest()
        manifest["initiative_id"] = "val-cli-fail"
        manifest["packets"][0]["validation_commands"] = ["false"]
        bi.apply_manifest(manifest)
        assert main(
            ["initiative", "start-attempt", "val-cli-fail", PACKET, "--json"]
        ) == 0
        attempt = json.loads(capsys.readouterr().out)
        assert main(
            ["initiative", "run-validation", str(attempt["id"]),
             "--cwd", str(tmp_path)]
        ) == 1
        assert "validation failed" in capsys.readouterr().out
