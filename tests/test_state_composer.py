"""Tests for state_composer — composed now-state, snapshots, mechanical diff (P1)."""

import time

import pytest

from gateway import signal_store, state_composer


@pytest.fixture(autouse=True)
def isolate_state_db(monkeypatch, tmp_path):
    """Point snapshots and signals at a temp kitty.db."""
    db_file = tmp_path / "kitty" / "kitty.db"
    monkeypatch.setattr(state_composer, "STATE_DB_FILE", db_file, raising=False)
    monkeypatch.setattr(signal_store, "SIGNALS_DB_FILE", db_file, raising=False)


@pytest.fixture
def stub_sources(monkeypatch):
    """Replace live sources with deterministic stubs."""
    sources = {
        "todos": lambda: {"open_count": 2, "latest": ["a", "b"]},
        "inbox": lambda: {"untriaged_count": 1},
    }
    monkeypatch.setattr(state_composer, "SOURCES", sources)
    return sources


def test_compose_now_returns_all_sections(stub_sources):
    state = state_composer.compose_now()

    assert isinstance(state["ts"], float)
    assert set(state["sections"]) == {"todos", "inbox"}
    assert state["sections"]["todos"] == {"ok": True, "open_count": 2, "latest": ["a", "b"]}


def test_failing_source_yields_error_section_not_whole_failure(monkeypatch):
    def broken():
        raise RuntimeError("store exploded")

    monkeypatch.setattr(
        state_composer,
        "SOURCES",
        {"good": lambda: {"n": 1}, "bad": broken},
    )

    sections = state_composer.compose_now()["sections"]

    assert sections["good"] == {"ok": True, "n": 1}
    assert sections["bad"]["ok"] is False
    assert "store exploded" in sections["bad"]["error"]


def test_slow_source_times_out_honestly(monkeypatch):
    def slow():
        time.sleep(0.5)
        return {"n": 1}

    monkeypatch.setattr(state_composer, "SOURCE_TIMEOUT_SECONDS", 0.1)
    monkeypatch.setattr(
        state_composer,
        "SOURCES",
        {"slow": slow, "fast": lambda: {"n": 2}},
    )

    sections = state_composer.compose_now()["sections"]

    assert sections["fast"]["ok"] is True
    assert sections["slow"]["ok"] is False
    assert "timed out" in sections["slow"]["error"]


def test_changes_without_snapshot_says_so(stub_sources):
    result = state_composer.changes_since_snapshot()

    assert result["baseline_ts"] is None
    assert result["changes"] == []
    assert result["new_signals"] == []
    assert "no snapshot yet" in result["note"]


def test_snapshot_then_diff_reports_scalar_changes(monkeypatch):
    counts = {"open": 2}
    monkeypatch.setattr(
        state_composer,
        "SOURCES",
        {"todos": lambda: {"open_count": counts["open"], "latest": ["x"]}},
    )

    snapshot = state_composer.snapshot_now()
    assert isinstance(snapshot["id"], int)

    counts["open"] = 5
    result = state_composer.changes_since_snapshot()

    assert result["baseline_ts"] == pytest.approx(snapshot["ts"])
    assert result["changes"] == [
        {"section": "todos", "field": "open_count", "before": 2, "after": 5}
    ]


def test_diff_ignores_list_fields(monkeypatch):
    items = {"latest": ["a"]}
    monkeypatch.setattr(
        state_composer,
        "SOURCES",
        {"todos": lambda: {"open_count": 1, "latest": items["latest"]}},
    )

    state_composer.snapshot_now()
    items["latest"] = ["a", "b"]

    assert state_composer.changes_since_snapshot()["changes"] == []


def test_source_going_down_is_a_reported_change(monkeypatch):
    healthy = {"up": True}

    def flappy():
        if not healthy["up"]:
            raise RuntimeError("connector down")
        return {"n": 1}

    monkeypatch.setattr(state_composer, "SOURCES", {"mail": flappy})

    state_composer.snapshot_now()
    healthy["up"] = False
    changes = state_composer.changes_since_snapshot()["changes"]

    assert {"section": "mail", "field": "ok", "before": True, "after": False} in changes


def test_new_signals_since_snapshot_are_included(stub_sources):
    state_composer.snapshot_now()
    time.sleep(0.01)
    signal_store.emit(source="mail", kind="message.received")

    result = state_composer.changes_since_snapshot()

    assert len(result["new_signals"]) == 1
    assert result["new_signals"][0]["kind"] == "message.received"


def test_real_sources_compose_against_isolated_stores(monkeypatch, tmp_path):
    """Smoke: the default SOURCES run against isolated store paths."""
    from gateway import chats_store, desktop_store, journal_store, todo_store

    db_file = tmp_path / "kitty" / "kitty.db"
    monkeypatch.setattr(todo_store, "TODO_DB_FILE", db_file, raising=False)
    # Point the legacy todo import at a path that does not exist so init_db()
    # never reads the real on-disk data/todos.db into the temp kitty.db.
    monkeypatch.setattr(todo_store, "TODO_DB", tmp_path / "todos-legacy-absent.db", raising=False)
    monkeypatch.setattr(chats_store, "CHATS_DB_FILE", db_file, raising=False)
    monkeypatch.setattr(journal_store, "JOURNAL_DB_FILE", db_file, raising=False)
    monkeypatch.setattr(
        journal_store, "LEGACY_JOURNAL_LOG", tmp_path / "journal.jsonl", raising=False
    )
    monkeypatch.setattr(chats_store, "LEGACY_CHATS_FILE", tmp_path / "chats.json", raising=False)
    inbox_file = tmp_path / "inbox.jsonl"
    monkeypatch.setattr(desktop_store, "INBOX_FILE", inbox_file, raising=False)
    # read_inbox/count take default args bound to the constant at def time,
    # so patch the section to pass the temp file explicitly.
    monkeypatch.setitem(
        state_composer.SOURCES,
        "inbox",
        lambda: {
            "total_count": desktop_store.count_inbox_entries(inbox_file=inbox_file),
            "untriaged_count": len(
                [
                    r
                    for r in desktop_store.read_inbox(limit=0, inbox_file=inbox_file)
                    if not r.get("processed")
                ]
            ),
            "latest_ts": None,
        },
    )

    todo_store.add("test the composer")
    desktop_store.append_text_capture(text="captured thought", inbox_file=inbox_file)

    sections = state_composer.compose_now()["sections"]

    assert sections["todos"]["ok"] is True
    assert sections["todos"]["open_count"] == 1
    assert sections["inbox"]["ok"] is True
    assert sections["inbox"]["untriaged_count"] == 1
    assert sections["journal"] == {"ok": True, "count": 0, "latest_ts": None}
    assert sections["chats"] == {"ok": True, "count": 0}
    assert sections["signals"]["ok"] is True
    assert sections["signals"]["unprocessed_count"] == 0
    # Calendar: on a machine without osascript this reads as an empty day
    # (known limitation noted in the composer); it must still be ok-shaped.
    assert "today_count" in sections["calendar"] or sections["calendar"]["ok"] is False
