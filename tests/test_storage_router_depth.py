"""Tests for the validation and telemetry behavior of the storage router.

These tests pin the deepening landed in Phase 1 of the gateway deepening
program — see
``docs/superpowers/specs/2026-06-24-gateway-deepening-program-design.md``.
"""

from __future__ import annotations

import json

import pytest

from gateway import storage_router


@pytest.fixture
def isolated_token_log(tmp_path, monkeypatch):
    log = tmp_path / "kitty_token_log.jsonl"
    monkeypatch.setattr(storage_router, "KITTY_TOKEN_LOG_FILE", log)
    return log


def _read_records(log) -> list[dict]:
    if not log.exists():
        return []
    return [json.loads(line) for line in log.read_text(encoding="utf-8").strip().splitlines()]


def test_add_todo_rejects_non_string_content(monkeypatch):
    def fake_add(*_args, **_kwargs):
        raise AssertionError("store should not be called when validation fails")

    monkeypatch.setattr(storage_router.todo_store, "add", fake_add)

    with pytest.raises(TypeError, match="content must be str"):
        storage_router.add_todo(123)  # type: ignore[arg-type]


def test_add_todo_rejects_non_string_status(monkeypatch):
    def fake_add(*_args, **_kwargs):
        raise AssertionError("store should not be called when validation fails")

    monkeypatch.setattr(storage_router.todo_store, "add", fake_add)

    with pytest.raises(TypeError, match="status must be str"):
        storage_router.add_todo("x", status=42)  # type: ignore[arg-type]


def test_replace_todos_rejects_non_list(monkeypatch):
    def fake_update(*_args, **_kwargs):
        raise AssertionError("store should not be called when validation fails")

    monkeypatch.setattr(storage_router.todo_store, "update", fake_update)

    with pytest.raises(TypeError, match="items must be a list"):
        storage_router.replace_todos({"not": "a list"})  # type: ignore[arg-type]


def test_complete_todo_rejects_non_int(monkeypatch):
    def fake_complete(*_args, **_kwargs):
        raise AssertionError("store should not be called when validation fails")

    monkeypatch.setattr(storage_router.todo_store, "complete_by_id", fake_complete)

    with pytest.raises(TypeError, match="todo_id must be int"):
        storage_router.complete_todo("42")  # type: ignore[arg-type]


def test_complete_todo_rejects_bool(monkeypatch):
    def fake_complete(*_args, **_kwargs):
        raise AssertionError("store should not be called when validation fails")

    monkeypatch.setattr(storage_router.todo_store, "complete_by_id", fake_complete)

    with pytest.raises(TypeError, match="todo_id must be int"):
        storage_router.complete_todo(True)  # type: ignore[arg-type]


def test_enable_plugin_rejects_non_string(monkeypatch):
    def fake_enable(*_args, **_kwargs):
        raise AssertionError("store should not be called when validation fails")

    monkeypatch.setattr(storage_router.plugin_registry, "enable", fake_enable)

    with pytest.raises(TypeError, match="name must be str"):
        storage_router.enable_plugin(7)  # type: ignore[arg-type]


def test_add_todo_emits_telemetry_record(monkeypatch, isolated_token_log):
    def fake_add(content, *, status, active_form):
        return {"id": 99, "content": content, "status": status, "active_form": active_form}

    monkeypatch.setattr(storage_router.todo_store, "add", fake_add)

    storage_router.add_todo("telemetry me", status="pending", active_form="")

    records = _read_records(isolated_token_log)
    assert len(records) == 1
    record = records[0]
    assert record["kind"] == "storage_write"
    assert record["store"] == "todos"
    assert record["op"] == "add"
    assert record["key"] == "99"
    assert isinstance(record["ms"], (int, float))
    assert record["ms"] >= 0


def test_enable_plugin_emits_telemetry_record(monkeypatch, isolated_token_log):
    def fake_enable(name):
        return True

    monkeypatch.setattr(storage_router.plugin_registry, "enable", fake_enable)

    storage_router.enable_plugin("telemetry-plugin")

    records = _read_records(isolated_token_log)
    assert len(records) == 1
    record = records[0]
    assert record["kind"] == "storage_write"
    assert record["store"] == "plugin_settings"
    assert record["op"] == "enable"
    assert record["key"] == "telemetry-plugin"


def test_telemetry_failure_does_not_block_write(monkeypatch, tmp_path):
    def fake_add(content, *, status, active_form):
        return {"id": 1, "content": content, "status": status, "active_form": active_form}

    monkeypatch.setattr(storage_router.todo_store, "add", fake_add)

    broken = tmp_path / "nonexistent_dir" / "wont_be_created" / "log.jsonl"
    monkeypatch.setattr(storage_router, "KITTY_TOKEN_LOG_FILE", broken)

    # The write must succeed even though telemetry can't open the file.
    result = storage_router.add_todo("no telemetry path")
    assert result["id"] == 1


def test_validation_failure_does_not_emit_telemetry(monkeypatch, isolated_token_log):
    """A rejected write must not produce a telemetry record."""
    with pytest.raises(TypeError):
        storage_router.add_todo(None)  # type: ignore[arg-type]

    assert _read_records(isolated_token_log) == []


def test_real_telemetry_uses_kitty_token_log_path(monkeypatch):
    """When telemetry can't write to the configured path, it falls back to
    ``paths.KITTY_TOKEN_LOG_FILE`` directly. This test pins the contract
    that ``storage_router.KITTY_TOKEN_LOG_FILE`` and ``paths.KITTY_TOKEN_LOG_FILE``
    start in sync.
    """
    from gateway import paths

    assert storage_router.KITTY_TOKEN_LOG_FILE == paths.KITTY_TOKEN_LOG_FILE
