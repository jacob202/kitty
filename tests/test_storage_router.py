"""Tests for the write-side storage router seam."""

from __future__ import annotations

import pytest

from gateway import plugin_registry, storage_router, todo_store


def _isolate_todo_store(monkeypatch, tmp_path):
    phase_b_db = tmp_path / "kitty" / "kitty.db"
    legacy_db = tmp_path / "legacy" / "todos.db"
    monkeypatch.setattr(todo_store, "TODO_DB_FILE", phase_b_db)
    monkeypatch.setattr(todo_store, "TODO_DB", legacy_db)


def _isolate_plugin_registry(monkeypatch, tmp_path):
    db_file = tmp_path / "kitty.db"
    legacy_file = tmp_path / "plugin_settings.json"
    monkeypatch.setattr(plugin_registry, "PLUGIN_DB_FILE", db_file)
    monkeypatch.setattr(plugin_registry, "PLUGIN_SETTINGS", legacy_file)
    plugin_registry.reset()


def test_replace_todos_delegates_to_todo_store(monkeypatch):
    calls: list[list[dict]] = []

    def fake_update(items: list[dict]) -> list[dict]:
        calls.append(items)
        return [{"content": "stored"}]

    monkeypatch.setattr(storage_router.todo_store, "update", fake_update)

    result = storage_router.replace_todos([{"content": "draft"}])

    assert calls == [[{"content": "draft"}]]
    assert result == [{"content": "stored"}]


def test_add_todo_delegates_to_todo_store(monkeypatch):
    def fake_add(content: str, *, status: str, active_form: str) -> dict:
        return {
            "content": content,
            "status": status,
            "active_form": active_form,
        }

    monkeypatch.setattr(storage_router.todo_store, "add", fake_add)

    result = storage_router.add_todo(
        "write seam",
        status="in_progress",
        active_form="routing writes",
    )

    assert result == {
        "content": "write seam",
        "status": "in_progress",
        "active_form": "routing writes",
    }


@pytest.mark.parametrize(
    ("router_func", "store_func"),
    [
        (storage_router.complete_todo, "complete_by_id"),
        (storage_router.delete_todo, "delete_by_id"),
    ],
)
def test_id_todo_mutations_delegate_to_todo_store(monkeypatch, router_func, store_func):
    calls: list[int] = []

    def fake_mutation(todo_id: int) -> bool:
        calls.append(todo_id)
        return True

    monkeypatch.setattr(storage_router.todo_store, store_func, fake_mutation)

    assert router_func(42) is True
    assert calls == [42]


def test_clear_todos_delegates_to_todo_store(monkeypatch):
    calls: list[str] = []

    def fake_clear() -> None:
        calls.append("clear")

    monkeypatch.setattr(storage_router.todo_store, "clear", fake_clear)

    storage_router.clear_todos()

    assert calls == ["clear"]


@pytest.mark.parametrize(
    ("router_func", "registry_func"),
    [
        (storage_router.enable_plugin, "enable"),
        (storage_router.disable_plugin, "disable"),
    ],
)
def test_plugin_mutations_delegate_to_registry(monkeypatch, router_func, registry_func):
    calls: list[str] = []

    def fake_registry_call(name: str) -> bool:
        calls.append(name)
        return True

    monkeypatch.setattr(storage_router.plugin_registry, registry_func, fake_registry_call)

    assert router_func("sample") is True
    assert calls == ["sample"]


def test_todo_errors_are_not_swallowed(monkeypatch):
    def broken_add(*_args, **_kwargs):
        raise RuntimeError("todo write failed")

    monkeypatch.setattr(storage_router.todo_store, "add", broken_add)

    with pytest.raises(RuntimeError, match="todo write failed"):
        storage_router.add_todo("boom")


def test_plugin_errors_are_not_swallowed(monkeypatch):
    def broken_enable(_name: str) -> bool:
        raise RuntimeError("plugin write failed")

    monkeypatch.setattr(storage_router.plugin_registry, "enable", broken_enable)

    with pytest.raises(RuntimeError, match="plugin write failed"):
        storage_router.enable_plugin("boom")


def test_router_writes_round_trip_through_real_stores(monkeypatch, tmp_path):
    _isolate_todo_store(monkeypatch, tmp_path)
    _isolate_plugin_registry(monkeypatch, tmp_path)

    added = storage_router.add_todo("router test todo")
    assert added["id"] > 0

    assert storage_router.complete_todo(added["id"]) is True
    rows = todo_store.get()
    match = next(todo for todo in rows if todo["id"] == added["id"])
    assert match["status"] == "completed"

    assert storage_router.delete_todo(added["id"]) is True

    plugin_registry.register("router-test-plugin", default_enabled=True)
    assert storage_router.disable_plugin("router-test-plugin") is True
    assert plugin_registry.is_enabled("router-test-plugin") is False
    assert storage_router.enable_plugin("router-test-plugin") is True
    assert plugin_registry.is_enabled("router-test-plugin") is True

    storage_router.clear_todos()
    assert todo_store.get() == []
