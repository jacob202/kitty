"""Tests for gateway/inbox_watcher.py"""

import json

import pytest

from gateway import paths


def test_ingest_writes_jsonl_and_deletes_file(tmp_path, monkeypatch):
    import gateway.inbox_watcher as iw

    inbox = tmp_path / "inbox.jsonl"
    monkeypatch.setattr(paths, "INBOX_FILE", inbox)
    monkeypatch.setattr(iw, "INBOX_FILE", inbox)
    md = tmp_path / "2026-06-23-1200.md"
    md.write_text("Phase D should use Postgres")

    iw._ingest(md)

    assert not md.exists()
    lines = inbox.read_text().strip().splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["text"] == "Phase D should use Postgres"
    assert entry["source"] == "icloud-inbox"


def test_ingest_skips_empty_file(tmp_path, monkeypatch):
    import gateway.inbox_watcher as iw

    inbox = tmp_path / "inbox.jsonl"
    monkeypatch.setattr(paths, "INBOX_FILE", inbox)
    monkeypatch.setattr(iw, "INBOX_FILE", inbox)
    md = tmp_path / "empty.md"
    md.write_text("   ")

    iw._ingest(md)

    assert not md.exists()
    assert not inbox.exists()


def test_poll_once_retries_once_then_raises(tmp_path, monkeypatch):
    import gateway.inbox_watcher as iw

    failing = tmp_path / "bad.md"
    failing.write_text("broken")
    monkeypatch.setattr(iw, "ICLOUD_INBOX", tmp_path)

    attempts = {"count": 0}

    def fail(_path):
        attempts["count"] += 1
        raise OSError("disk full")

    monkeypatch.setattr(iw, "_ingest", fail)

    with pytest.raises(RuntimeError, match="failed to ingest bad.md after retry"):
        iw._poll_once()

    assert attempts["count"] == 2


@pytest.mark.asyncio
async def test_watch_loop_waits_for_missing_directory(tmp_path, monkeypatch):
    import gateway.inbox_watcher as iw

    missing = tmp_path / "missing"
    monkeypatch.setattr(iw, "ICLOUD_INBOX", missing)
    monkeypatch.setattr(iw, "POLL_INTERVAL", 0)

    async def stop(_seconds):
        raise RuntimeError("stop-loop")

    monkeypatch.setattr(iw.asyncio, "sleep", stop)

    with pytest.raises(RuntimeError, match="stop-loop"):
        await iw.watch_loop()
