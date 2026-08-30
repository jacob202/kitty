from __future__ import annotations

from datetime import datetime, timedelta, timezone


def _store(tmp_path, monkeypatch):
    from gateway import explicit_memory

    monkeypatch.setattr(explicit_memory, "DB_FILE", tmp_path / "kitty.db")
    return explicit_memory


def test_explicit_memory_survives_correction_with_provenance(tmp_path, monkeypatch):
    store = _store(tmp_path, monkeypatch)
    old = store.remember(
        "I prefer dark mode",
        namespace="preferences",
        memory_key="ui.theme",
        source_kind="user_explicit",
        source_ref="conversation:c1",
    )
    new = store.remember(
        "Use light mode now",
        namespace="preferences",
        memory_key="ui.theme",
        source_kind="user_correction",
        source_ref="conversation:c2",
    )

    active = store.search("theme light mode", limit=5)
    assert [row["id"] for row in active] == [new["id"]]
    assert active[0]["source_kind"] == "user_correction"
    assert active[0]["source_ref"] == "conversation:c2"
    superseded = store.get(old["id"], include_inactive=True)
    assert superseded["status"] == "superseded"
    assert superseded["superseded_by"] == new["id"]


def test_forget_suppresses_explicit_memory_without_erasing_history(tmp_path, monkeypatch):
    store = _store(tmp_path, monkeypatch)
    row = store.remember("My favorite editor is Zed", memory_key="editor")

    assert store.forget(row["id"]) is True
    assert store.search("favorite editor Zed", limit=5) == []
    forgotten = store.get(row["id"], include_inactive=True)
    assert forgotten["status"] == "forgotten"
    assert forgotten["forgotten_at"] is not None


def test_stable_explicit_fact_truth_does_not_decay_with_age(tmp_path, monkeypatch):
    store = _store(tmp_path, monkeypatch)
    old_time = datetime.now(timezone.utc) - timedelta(days=3650)
    store.remember(
        "My birthday is January 1, 1987",
        memory_key="profile.birthday",
        now=old_time,
    )

    [row] = store.search("birthday January 1987", limit=5)
    assert row["truth_confidence"] == 1.0
    assert row["created_at"].startswith(str(old_time.year))


def test_explicit_search_does_not_return_unrelated_sensitive_context(tmp_path, monkeypatch):
    store = _store(tmp_path, monkeypatch)
    store.remember(
        "Private support preference that is unrelated to coding",
        memory_key="support.private",
        sensitivity="sensitive",
    )

    assert store.search("what is the Kitty build status", limit=5) == []


def test_explicit_store_rejects_project_namespace(tmp_path, monkeypatch):
    store = _store(tmp_path, monkeypatch)

    import pytest

    with pytest.raises(store.ExplicitMemoryError, match="namespace"):
        store.remember("Kitty is complete", namespace="projects")


def test_explicit_correction_rejects_conflicting_key(tmp_path, monkeypatch):
    store = _store(tmp_path, monkeypatch)
    old = store.remember("I prefer dark mode", memory_key="ui.theme")

    import pytest

    with pytest.raises(store.ExplicitMemoryError, match="memory_key"):
        store.remember(
            "Use light mode now",
            memory_key="editor",
            supersedes_id=old["id"],
        )

    assert store.get(old["id"])["status"] == "active"
