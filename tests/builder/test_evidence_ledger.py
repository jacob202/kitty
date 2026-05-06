import json

from src.builder.evidence_ledger import append_evidence


def test_append_evidence_writes_jsonl(tmp_path):
    ledger = tmp_path / "builder_evidence.jsonl"
    append_evidence(
        ledger,
        run_id="run-1",
        raw_input_hash="abc",
        outcome="recommended",
        workers=["single_worker"],
        files_changed=[],
        commands_run=["venv/bin/python -m pytest tests/builder -q"],
        risks=["not executed yet"],
    )
    row = json.loads(ledger.read_text(encoding="utf-8").strip())
    assert row["run_id"] == "run-1"
    assert row["outcome"] == "recommended"
    assert row["commands_run"] == ["venv/bin/python -m pytest tests/builder -q"]
