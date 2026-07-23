"""Tests for gateway/builder_report.py — CP-05 campaign report artifact."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from gateway import builder_attempt as ba
from gateway import builder_initiative as bi
from gateway import builder_queue as bq
from gateway import builder_report as br


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    p = tmp_path / "kittybuilder" / "builder_queue.db"
    bi.init_db(p)
    return p


def _manifest(initiative_id: str = "report-v1") -> dict:
    return {
        "manifest_version": 1,
        "initiative_id": initiative_id,
        "title": "Report test",
        "description": "d",
        "packets": [
            {
                "id": "R1",
                "title": "First",
                "objective": "one",
                "acceptance_criteria": ["ok"],
                "allowed_paths": ["gateway/a.py"],
                "policy": {"max_attempts": 2},
            },
            {
                "id": "R2",
                "title": "Second",
                "objective": "two",
                "depends_on": ["R1"],
                "acceptance_criteria": ["ok"],
                "allowed_paths": ["gateway/b.py"],
            },
        ],
    }


class TestCp05ReportGeneration:
    def test_report_generated_for_in_flight_initiative(self, db_path: Path, tmp_path: Path):
        bi.apply_manifest(_manifest(), db_path=db_path)
        out_dir = tmp_path / "reports"

        path = br.generate_report(
            "report-v1", db_path=db_path, out_dir=out_dir, timestamp="20260101T000000Z"
        )

        assert path.exists()
        assert path.name == "report-v1-20260101T000000Z.md"
        content = path.read_text()
        assert "Campaign report: report-v1" in content
        assert "## R1" in content
        assert "## R2" in content

    def test_report_generated_for_finished_initiative(self, db_path: Path, tmp_path: Path):
        result = bi.apply_manifest(_manifest(), db_path=db_path)
        for mapping in result["packets"]:
            task_id = mapping["task_id"]
            bq.transition_task(task_id, bq.CLAIMED, db_path=db_path)
            bq.transition_task(task_id, bq.RUNNING, db_path=db_path)
            bq.transition_task(task_id, bq.PR_OPENED, db_path=db_path)
            bq.transition_task(task_id, bq.AWAITING_REVIEW, db_path=db_path)
            bq.transition_task(task_id, bq.DONE, db_path=db_path)

        path = br.generate_report(
            "report-v1", db_path=db_path, out_dir=tmp_path / "reports", timestamp="ts"
        )

        content = path.read_text()
        assert "`done`" in content
        assert "packets: 2 (done 2" in content

    def test_report_includes_validation_and_review_evidence(self, db_path: Path, tmp_path: Path):
        bi.apply_manifest(_manifest(), db_path=db_path)
        attempt = ba.start_attempt("report-v1", "R1", db_path=db_path)
        ba.record_implementation_result(
            attempt["id"],
            {"contract_version": ba.CONTRACT_VERSION, "status": "completed", "summary": "s"},
            db_path=db_path,
        )
        ba.record_review_result(
            attempt["id"],
            {"contract_version": ba.CONTRACT_VERSION, "verdict": "approve", "summary": "looks good"},
            db_path=db_path,
        )

        path = br.generate_report(
            "report-v1", db_path=db_path, out_dir=tmp_path / "reports", timestamp="ts"
        )
        content = path.read_text()
        assert "approve" in content
        assert "looks good" in content
        assert "run-manifest.json" in content

    def test_report_includes_stop_class_from_cp03_events(self, db_path: Path, tmp_path: Path):
        result = bi.apply_manifest(_manifest(), db_path=db_path)
        task_id = result["packets"][0]["task_id"]
        bq.append_event(
            task_id,
            "initiative_decision",
            payload={
                "stop_class": "needs_decision",
                "stop_class_reason": "requirement may be ambiguous",
            },
            db_path=db_path,
        )

        path = br.generate_report(
            "report-v1", db_path=db_path, out_dir=tmp_path / "reports", timestamp="ts"
        )
        content = path.read_text()
        assert "needs_decision" in content
        assert "requirement may be ambiguous" in content

    def test_validation_tail_is_capped(self, db_path: Path, tmp_path: Path):
        bi.apply_manifest(_manifest(), db_path=db_path)
        attempt = ba.start_attempt("report-v1", "R1", db_path=db_path)
        ba.record_implementation_result(
            attempt["id"],
            {"contract_version": ba.CONTRACT_VERSION, "status": "completed", "summary": "s"},
            db_path=db_path,
        )
        # Fabricate a validation result directly (bypassing subprocess) with an
        # oversized output tail to prove the report caps it independently of
        # run_validation's own OUTPUT_CAP.
        conn = bq.connect(db_path)
        try:
            import json as _json

            huge = "x" * 5000
            conn.execute(
                "UPDATE packet_attempts SET validation_json = ? WHERE id = ?",
                (
                    _json.dumps(
                        {
                            "status": "passed",
                            "commands": [
                                {
                                    "command": "true",
                                    "exit_code": 0,
                                    "passed": True,
                                    "duration_s": 0.1,
                                    "output_tail": huge,
                                }
                            ],
                        }
                    ),
                    attempt["id"],
                ),
            )
            conn.commit()
        finally:
            conn.close()

        path = br.generate_report(
            "report-v1", db_path=db_path, out_dir=tmp_path / "reports", timestamp="ts"
        )
        content = path.read_text()
        assert "x" * 5000 not in content
        assert len(content) < 5000  # the whole report must not balloon with the raw tail

    def test_changed_paths_list_is_capped(self, db_path: Path, tmp_path: Path):
        import json as _json

        result = bi.apply_manifest(_manifest(), db_path=db_path)
        task_id = result["packets"][0]["task_id"]
        many_paths = [f"gateway/file_{i}.py" for i in range(50)]
        conn = sqlite3.connect(db_path)
        try:
            conn.execute(
                """
                INSERT INTO runs (id, task_id, state, command_json, final_report_json)
                VALUES (?, ?, 'succeeded', '[]', ?)
                """,
                ("run_test_1", task_id, _json.dumps({"changed_paths": many_paths})),
            )
            conn.commit()
        finally:
            conn.close()

        path = br.generate_report(
            "report-v1", db_path=db_path, out_dir=tmp_path / "reports", timestamp="ts"
        )
        content = path.read_text()
        assert "more not shown" in content
        # Only the capped prefix of filenames should appear verbatim.
        assert "file_49.py" not in content

    def test_generate_report_does_not_write_to_queue_db(self, db_path: Path, tmp_path: Path):
        bi.apply_manifest(_manifest(), db_path=db_path)
        before = sqlite3.connect(db_path).execute(
            "SELECT COUNT(*) FROM events"
        ).fetchone()[0]

        br.generate_report("report-v1", db_path=db_path, out_dir=tmp_path / "reports", timestamp="ts")

        after = sqlite3.connect(db_path).execute(
            "SELECT COUNT(*) FROM events"
        ).fetchone()[0]
        assert after == before

    def test_report_raises_for_unknown_initiative(self, db_path: Path, tmp_path: Path):
        with pytest.raises(bi.InitiativeNotFoundError):
            br.generate_report("ghost", db_path=db_path, out_dir=tmp_path / "reports")


@pytest.fixture
def cli_db(tmp_path: Path, monkeypatch) -> Path:
    """Point the module-level default DB (and report output dir) at tmp_path."""
    p = tmp_path / "kittybuilder" / "builder_queue.db"
    monkeypatch.setattr(bq, "BUILDER_QUEUE_DB", p)
    monkeypatch.setattr(br, "REPORTS_DIR", p.parent / "reports")
    return p


def _write_manifest(tmp_path: Path, manifest: dict) -> Path:
    import json

    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path


class TestCp05ReportCli:
    def test_cli_report_writes_file_and_prints_path(self, tmp_path, cli_db, capsys):
        from gateway.builder_cli import main

        manifest_path = _write_manifest(tmp_path, _manifest("report-cli-v1"))

        assert main(["initiative", "apply", str(manifest_path)]) == 0
        capsys.readouterr()

        assert main(["initiative", "report", "report-cli-v1"]) == 0
        out = capsys.readouterr().out
        assert "report written:" in out
        assert (cli_db.parent / "reports").exists()

    def test_cli_report_missing_initiative(self, cli_db, capsys):
        from gateway.builder_cli import main

        assert main(["initiative", "report", "ghost"]) == 1
        assert "not found" in capsys.readouterr().err
