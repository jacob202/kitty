from __future__ import annotations

from types import SimpleNamespace

import pytest

from gateway import cron, image_characters, image_sessions, undo_journal
from gateway.routes import cron as cron_routes
from gateway.routes import extended, loops, memories


@pytest.mark.asyncio
async def test_explicit_memory_delete_returns_undo_receipt(monkeypatch):
    seen: list[str] = []
    monkeypatch.setattr(
        undo_journal,
        "forget_memory_with_undo",
        lambda memory_id: seen.append(memory_id) or "undo_memory_1",
    )

    result = await memories.delete_memory("exp_123")

    assert seen == ["exp_123"]
    assert result["undo_journal_id"] == "undo_memory_1"


@pytest.mark.asyncio
async def test_memory_correction_returns_undo_receipt(monkeypatch):
    seen: list[tuple[str, str, str | None]] = []
    monkeypatch.setattr(
        undo_journal,
        "correct_memory_with_undo",
        lambda memory_id, text, memory_key=None: seen.append((memory_id, text, memory_key)) or "undo_memory_2",
    )
    monkeypatch.setattr(
        undo_journal,
        "get",
        lambda journal_id: {"after": {"id": "exp_corrected"}},
    )
    monkeypatch.setattr("gateway.memory_explain.explain", lambda memory_id: {"id": memory_id})

    result = await memories.correct_memory(
        "exp_123", memories.CorrectMemoryRequest(text="corrected", memory_key="city")
    )

    assert seen == [("exp_123", "corrected", "city")]
    assert result["memory"]["id"] == "exp_corrected"
    assert result["undo_journal_id"] == "undo_memory_2"


@pytest.mark.asyncio
async def test_character_patch_returns_undo_receipt(monkeypatch):
    seen: list[tuple[str, dict]] = []
    monkeypatch.setattr(
        undo_journal,
        "update_character_with_undo",
        lambda character_id, **fields: seen.append((character_id, fields)) or "undo_char_1",
    )
    monkeypatch.setattr(
        image_characters,
        "get_character",
        lambda character_id: SimpleNamespace(to_dict=lambda: {"character_id": character_id, "name": "Aria v2"}),
    )

    result = await extended.studio_update_character(
        "char_1", extended.CharacterUpdate(name="Aria v2")
    )

    assert seen[0][0] == "char_1"
    assert seen[0][1]["name"] == "Aria v2"
    assert result["undo_journal_id"] == "undo_char_1"


@pytest.mark.asyncio
async def test_loop_toggle_returns_undo_receipt(monkeypatch):
    monkeypatch.setattr(undo_journal, "toggle_automation_with_undo", lambda sid: "undo_loop_1")
    monkeypatch.setattr(
        cron,
        "list_schedules",
        lambda: [{"id": "loop_1", "name": "Loop", "enabled": 0, "metadata": "{}"}],
    )

    result = await loops.toggle_loop("loop_1")

    assert result["status"] == "paused"
    assert result["undo_journal_id"] == "undo_loop_1"


@pytest.mark.asyncio
async def test_cron_update_and_toggle_return_undo_receipts(monkeypatch):
    monkeypatch.setattr(undo_journal, "update_automation_with_undo", lambda *args, **kwargs: "undo_cron_update")
    monkeypatch.setattr(undo_journal, "toggle_automation_with_undo", lambda sid: "undo_cron_toggle")
    monkeypatch.setattr(cron, "list_schedules", lambda: [{"id": "sched_1", "enabled": 1}])

    updated = await cron_routes.cron_update_schedule(
        "sched_1",
        cron_routes.ScheduleRequest(
            name="Morning", action="brief", schedule_type="daily", schedule_value="07:00"
        ),
    )
    toggled = await cron_routes.cron_toggle_schedule("sched_1")

    assert updated == {"ok": True, "undo_journal_id": "undo_cron_update"}
    assert toggled == {"ok": True, "undo_journal_id": "undo_cron_toggle"}


@pytest.mark.asyncio
async def test_anchor_set_returns_undo_receipt(monkeypatch):
    monkeypatch.setattr(undo_journal, "set_anchor_with_undo", lambda session_id, job_id: "undo_anchor_1")
    session = SimpleNamespace(session_id="imgses_1")
    monkeypatch.setattr(image_sessions, "require_session", lambda session_id: session)
    monkeypatch.setattr(
        extended,
        "session_payload",
        lambda value: {"session_id": value.session_id, "anchor_job_id": "job_1"},
    )

    result = await extended.studio_set_anchor("imgses_1", extended.AnchorRequest(job_id="job_1"))

    assert result["anchor_job_id"] == "job_1"
    assert result["undo_journal_id"] == "undo_anchor_1"
