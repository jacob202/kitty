"""RED→GREEN tests for the unified activity timeline projection (Packet 08)."""

from __future__ import annotations

import pytest

from gateway import (
    action_grants,
    activity_timeline,
    automation_runs,
    explicit_memory,
    image_jobs,
    paths,
    signal_store,
)


@pytest.fixture()
def _timeline_db(tmp_path, monkeypatch):
    db_file = tmp_path / "kitty.db"
    monkeypatch.setattr(paths, "KITTY_DB_FILE", db_file)
    monkeypatch.setattr(automation_runs, "DB_FILE", db_file)
    monkeypatch.setattr(explicit_memory, "DB_FILE", db_file)
    monkeypatch.setattr(signal_store, "SIGNALS_DB_FILE", db_file)
    monkeypatch.setattr(action_grants, "GRANTS_DB_FILE", db_file)
    return db_file


def _run(automation_id, action, started_at, status="completed", error=None):
    run = automation_runs.begin_run(
        automation_id=automation_id,
        action=action,
        trigger_kind="time",
        started_at=started_at,
    )
    return automation_runs.finish_run(
        run["id"], status=status, completed_at=started_at + 1, error=error
    )


def test_entries_are_newest_first(_timeline_db):
    _run("a1", "brief", 100)
    _run("a2", "monitor", 300)
    _run("a3", "cleanup", 200)

    entries = activity_timeline.build_timeline(limit=50)

    timestamps = [e["timestamp"] for e in entries]
    assert timestamps == sorted(timestamps, reverse=True)
    assert [e["object"] for e in entries] == ["a2", "a3", "a1"]


def test_limit_is_bounded(_timeline_db):
    for i in range(10):
        _run(f"a{i}", "act", 1000 + i)

    assert len(activity_timeline.build_timeline(limit=3)) == 3


def test_mixed_sources_are_assembled(_timeline_db):
    _run("a1", "brief", 100)
    image_jobs.create_job("comfyui", "txt2img", prompt="a wizard")
    explicit_memory.remember(
        "Preferred editor: VS Code", namespace="preferences", source_kind="user_explicit"
    )
    signal_store.emit(source="web_monitor", kind="checked", ts=500)
    action_grants.create_grant(
        capability="image_generation",
        decision="deny",
        granted_tier="T1",
        reason="test",
        created_by="system",
    )

    entries = activity_timeline.build_timeline(limit=50)

    sources = {e["source"] for e in entries}
    assert sources >= {"automation", "image", "memory", "signal", "grant"}


def test_failures_filter_surfaces_failed_operations(_timeline_db):
    _run("ok", "brief", 100, status="completed")
    _run("bad", "monitor", 200, status="failed", error="timeout")

    entries = activity_timeline.build_timeline(filter="failures", limit=50)

    assert [e["object"] for e in entries] == ["bad"]
    assert entries[0]["failed"] is True
    assert entries[0]["detail"] == "timeout"


def test_sensitive_memory_is_excluded(_timeline_db):
    explicit_memory.remember("secret thing", namespace="facts", sensitivity="sensitive")
    explicit_memory.remember("public thing", namespace="facts")

    entries = activity_timeline.build_timeline(filter="memory", limit=50)

    summaries = [e["summary"] for e in entries]
    assert "secret thing" not in summaries
    assert "public thing" in summaries


def test_no_duplicate_projection_entries(_timeline_db):
    _run("a1", "brief", 100)
    _run("a2", "monitor", 200)

    entries = activity_timeline.build_timeline(limit=50)

    keys = [(e["source"], e["evidence"]) for e in entries]
    assert len(keys) == len(set(keys))


def test_missing_optional_evidence_still_renders(_timeline_db):
    _run("a1", "brief", 100, status="completed")

    entry = activity_timeline.build_timeline(limit=50)[0]

    assert entry["detail"] is None
    assert entry["evidence"]


def test_invalid_filter_fails_loud(_timeline_db):
    with pytest.raises(ValueError):
        activity_timeline.build_timeline(filter="bogus")


def test_malformed_required_timestamp_fails_loud(_timeline_db, monkeypatch):
    monkeypatch.setattr(automation_runs, "list_runs", lambda **_kwargs: [{
        "id": "bad-run", "automation_id": "a1", "action": "brief",
        "status": "failed", "started_at": "not-a-timestamp", "completed_at": None,
        "error": "bad timestamp",
    }])
    with pytest.raises(ValueError, match="invalid timeline timestamp"):
        activity_timeline.build_timeline(filter="automations")


def test_revoked_grant_uses_revocation_time(_timeline_db, monkeypatch):
    grant = action_grants.create_grant(
        capability="image_generation", decision="deny", granted_tier="T1",
        reason="test", created_by="system",
    )
    monkeypatch.setattr(action_grants.time, "time", lambda: 999.0)
    action_grants.revoke_grant(grant["id"])

    entries = activity_timeline.build_timeline(filter="system", limit=50)
    revoked = next(e for e in entries if e["source"] == "grant")
    assert revoked["status"] == "revoked"
    assert revoked["timestamp"] == 999.0


def test_failures_filter_does_not_lose_older_failures_behind_success_limit(_timeline_db):
    _run("old-failure", "monitor", 1, status="failed", error="timeout")
    for i in range(60):
        _run(f"ok-{i}", "brief", 100 + i, status="completed")

    entries = activity_timeline.build_timeline(filter="failures", limit=10)
    assert any(e["object"] == "old-failure" for e in entries)
