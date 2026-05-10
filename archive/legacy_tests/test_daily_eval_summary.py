import json
from datetime import UTC, date, datetime
from pathlib import Path

from scripts import daily_eval_summary as summary


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_summarize_day_aggregates_smoke_and_daily_flow(tmp_path):
    artifact_dir = tmp_path / "artifacts"
    artifact_dir.mkdir()

    day = date(2026, 5, 7)
    ts = datetime(2026, 5, 7, 15, 30, tzinfo=UTC).timestamp()
    other_ts = datetime(2026, 5, 6, 11, 0, tzinfo=UTC).timestamp()

    _write_json(
        artifact_dir / "abc_smoke.json",
        {
            "run_id": "abc",
            "suite": "smoke",
            "started_at": ts,
            "scores": {"smoke": {"passed": 5, "total": 5, "rate": 1.0}},
        },
    )
    _write_json(
        artifact_dir / "def_smoke.json",
        {
            "run_id": "def",
            "suite": "smoke",
            "started_at": ts,
            "scores": {"smoke": {"passed": 4, "total": 5, "rate": 0.8}},
        },
    )
    _write_json(
        artifact_dir / "daily_flow_a.json",
        {
            "run_id": "daily_flow_a",
            "suite": "daily_flow",
            "started_at": "20260507T210000Z",
            "scores": {"daily_flow": {"passed": 4, "total": 5, "rate": 0.8}},
            "checks": [
                {"name": "chat_responds", "passed": False},
                {"name": "brief_available", "passed": True},
            ],
        },
    )
    _write_json(
        artifact_dir / "browser_flow_a.json",
        {
            "run_id": "browser_flow_a",
            "suite": "browser_flow",
            "started_at": "20260507T220000Z",
            "scores": {"browser_flow": {"passed": 3, "total": 4, "rate": 0.75}},
            "checks": [
                {"name": "voice_state_transitions", "passed": False},
                {"name": "page_load", "passed": True},
            ],
        },
    )
    _write_json(
        artifact_dir / "old_smoke.json",
        {
            "run_id": "old",
            "suite": "smoke",
            "started_at": other_ts,
            "scores": {"smoke": {"passed": 0, "total": 5, "rate": 0.0}},
        },
    )
    (artifact_dir / "broken.json").write_text("{not-json}", encoding="utf-8")

    result = summary.summarize_day(artifact_dir=artifact_dir, summary_date=day)

    assert result["date"] == "2026-05-07"
    assert result["scanned_artifacts"] == 6
    assert result["matched_artifacts"] == 4
    assert result["parse_errors"] == 1

    assert result["smoke"]["runs"] == 2
    assert result["smoke"]["avg_rate"] == 0.9
    assert result["smoke"]["aggregated_rate"] == 0.9
    assert result["smoke"]["passed"] == 9
    assert result["smoke"]["total"] == 10

    assert result["daily_flow"]["runs"] == 1
    assert result["daily_flow"]["avg_rate"] == 0.8
    assert result["daily_flow"]["aggregated_rate"] == 0.8
    assert result["daily_flow"]["failing_checks"] == [{"name": "chat_responds", "failures": 1}]
    assert result["browser_flow"]["runs"] == 1
    assert result["browser_flow"]["avg_rate"] == 0.75
    assert result["browser_flow"]["aggregated_rate"] == 0.75
    assert result["browser_flow"]["failing_checks"] == [{"name": "voice_state_transitions", "failures": 1}]


def test_write_summary_outputs_json_and_markdown(tmp_path):
    payload = {
        "date": "2026-05-07",
        "generated_at": "2026-05-07T22:00:00+00:00",
        "artifact_dir": "/tmp/artifacts",
        "scanned_artifacts": 3,
        "matched_artifacts": 2,
        "parse_errors": 0,
        "smoke": {"runs": 1, "avg_rate": 1.0, "aggregated_rate": 1.0, "passed": 5, "total": 5},
        "daily_flow": {
            "runs": 1,
            "avg_rate": 0.8,
            "aggregated_rate": 0.8,
            "passed": 4,
            "total": 5,
            "failing_checks": [{"name": "chat_responds", "failures": 1}],
        },
        "browser_flow": {
            "runs": 1,
            "avg_rate": 0.75,
            "aggregated_rate": 0.75,
            "passed": 3,
            "total": 4,
            "failing_checks": [{"name": "voice_state_transitions", "failures": 1}],
        },
    }

    json_path, md_path = summary.write_summary(payload, output_dir=tmp_path / "summaries")

    assert json_path.exists()
    assert md_path.exists()

    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert data["date"] == "2026-05-07"
    text = md_path.read_text(encoding="utf-8")
    assert "# Daily Eval Summary - 2026-05-07" in text
    assert "chat_responds: 1" in text
    assert "voice_state_transitions: 1" in text
