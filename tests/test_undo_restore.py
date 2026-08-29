"""Undo/Restore tests (Packet 09)."""

from __future__ import annotations

import pytest

from gateway import db as kitty_db
from gateway import paths


@pytest.fixture
def _db(tmp_path, monkeypatch):
    """Point every evidence store at one shared temp DB and migrate it."""
    from gateway import (
        cron,
        explicit_memory,
        image_characters,
        undo_journal,
    )

    db = tmp_path / "kitty.db"
    monkeypatch.setattr(paths, "KITTY_DB_FILE", db)
    monkeypatch.setattr(undo_journal, "DB_FILE", db)
    monkeypatch.setattr(cron, "KITTY_DB_FILE", db)
    monkeypatch.setattr(explicit_memory, "DB_FILE", db)
    monkeypatch.setattr(image_characters, "KITTY_DB_FILE", db)
    kitty_db.migrate(db_file=db)
    return db


def test_character_undo_restores_prior_profile(_db):
    from gateway import image_characters, undo_journal

    char = image_characters.create_character(
        "Aria", description="a musician", identity_preset="balanced"
    )
    journal_id = undo_journal.update_character_with_undo(
        char.character_id, name="Aria v2", description="a painter"
    )

    assert image_characters.get_character(char.character_id).name == "Aria v2"

    result = undo_journal.undo(journal_id)

    restored = image_characters.get_character(char.character_id)
    assert restored.name == "Aria"
    assert restored.description == "a musician"
    assert result["restored"] == "character"


def test_memory_forget_undo_restores_a_new_active_memory(_db):
    from gateway import explicit_memory, undo_journal

    memory = explicit_memory.remember(
        "Preferred editor: VS Code", namespace="preferences"
    )
    journal_id = undo_journal.forget_memory_with_undo(memory["id"])

    assert explicit_memory.get(memory["id"]) is None

    undo_journal.undo(journal_id)

    active = explicit_memory.list_memories(namespace="preferences")
    assert any(r["text"] == "Preferred editor: VS Code" for r in active)


def test_sensitive_forget_undo_is_refused(_db):
    from gateway import explicit_memory, undo_journal

    memory = explicit_memory.remember(
        "a private detail", namespace="facts", sensitivity="sensitive"
    )
    journal_id = undo_journal.forget_memory_with_undo(memory["id"])

    with pytest.raises(undo_journal.UndoError):
        undo_journal.undo(journal_id)

    assert explicit_memory.get(memory["id"]) is None


def test_memory_correct_undo_reverts_to_prior_text(_db):
    from gateway import explicit_memory, undo_journal

    memory = explicit_memory.remember("city: Austin", namespace="facts", memory_key="city")
    journal_id = undo_journal.correct_memory_with_undo(memory["id"], "city: Dallas")

    def active_city_text():
        rows = [
            r
            for r in explicit_memory.list_memories(namespace="facts", include_inactive=True)
            if r["memory_key"] == "city" and r["status"] == "active"
        ]
        return [r["text"] for r in rows]

    assert active_city_text() == ["city: Dallas"]

    undo_journal.undo(journal_id)

    assert active_city_text() == ["city: Austin"]


def test_repeated_undo_unwinds_two_changes(_db):
    from gateway import image_characters, undo_journal

    char = image_characters.create_character("Aria")
    first = undo_journal.update_character_with_undo(char.character_id, name="Aria v2")
    second = undo_journal.update_character_with_undo(char.character_id, name="Aria v3")

    assert image_characters.get_character(char.character_id).name == "Aria v3"

    undo_journal.undo(second)
    assert image_characters.get_character(char.character_id).name == "Aria v2"

    undo_journal.undo(first)
    assert image_characters.get_character(char.character_id).name == "Aria"


def test_conflicting_newer_change_blocks_undo(_db):
    from gateway import image_characters, undo_journal

    char = image_characters.create_character("Aria")
    first = undo_journal.update_character_with_undo(char.character_id, name="Aria v2")
    undo_journal.update_character_with_undo(char.character_id, name="Aria v3")

    with pytest.raises(undo_journal.UndoConflict):
        undo_journal.undo(first)


def test_already_undone_fails_loud(_db):
    from gateway import image_characters, undo_journal

    char = image_characters.create_character("Aria")
    journal_id = undo_journal.update_character_with_undo(char.character_id, name="Aria v2")

    undo_journal.undo(journal_id)

    with pytest.raises(undo_journal.UndoError):
        undo_journal.undo(journal_id)


def test_evidence_is_preserved(_db):
    from gateway import image_characters, undo_journal

    char = image_characters.create_character("Aria")
    journal_id = undo_journal.update_character_with_undo(char.character_id, name="Aria v2")

    entry = undo_journal.get(journal_id)
    assert entry is not None
    assert entry["before"]["name"] == "Aria"
    assert entry["after"]["name"] == "Aria v2"
    assert entry["undone"] is False

    history = undo_journal.list_history("character", char.character_id)
    assert any(e["id"] == journal_id for e in history)


def test_image_anchor_undo_restores_and_lineage_intact(_db):
    from gateway import image_jobs, image_sessions, undo_journal
    from gateway.image_jobs import ImageJobStatus

    session = image_sessions.create_session()
    job = image_jobs.create_job("comfyui", "txt2img", prompt="a wizard")
    image_jobs.transition(job.job_id, ImageJobStatus.SUBMITTED)
    image_jobs.transition(job.job_id, ImageJobStatus.RUNNING)
    image_jobs.update_job(job.job_id, artifact_id="art_1", output_path="/tmp/wizard.png")
    image_jobs.transition(job.job_id, ImageJobStatus.SUCCEEDED)
    image_sessions.attach_job(session.session_id, job.job_id)

    journal_id = undo_journal.set_anchor_with_undo(session.session_id, job.job_id)
    assert image_sessions.get_session(session.session_id).anchor_job_id == job.job_id

    undo_journal.undo(journal_id)

    assert image_sessions.get_session(session.session_id).anchor_job_id is None
    # lineage/evidence must be untouched by undo
    persisted = image_jobs.get_job(job.job_id)
    assert persisted.status == ImageJobStatus.SUCCEEDED
    assert persisted.artifact_id == "art_1"
