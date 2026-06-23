"""Tests for gateway/inbox_watcher.py"""

import json


def test_ingest_writes_jsonl_and_deletes_file(tmp_path, monkeypatch):
    import gateway.inbox_watcher as iw

    monkeypatch.setattr(iw, "INBOX_JSONL", tmp_path / "inbox.jsonl")
    md = tmp_path / "2026-06-23-1200.md"
    md.write_text("Phase D should use Postgres")

    iw._ingest(md)

    assert not md.exists()
    lines = (tmp_path / "inbox.jsonl").read_text().strip().splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["text"] == "Phase D should use Postgres"
    assert entry["source"] == "icloud-inbox"


def test_ingest_skips_empty_file(tmp_path, monkeypatch):
    import gateway.inbox_watcher as iw

    monkeypatch.setattr(iw, "INBOX_JSONL", tmp_path / "inbox.jsonl")
    md = tmp_path / "empty.md"
    md.write_text("   ")

    iw._ingest(md)

    assert not md.exists()
    assert not (tmp_path / "inbox.jsonl").exists()
