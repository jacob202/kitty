"""Tests for the storage router port."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from gateway import db as kitty_db
from gateway import storage_router as store
from gateway.storage_router import (
    ReadQuery,
    StorageError,
    StorageRouter,
    StoreSpec,
    _JsonlAdapter,
    _JsonAdapter,
    _PluginSettingsAdapter,
)


@pytest.fixture(autouse=True)
def _reset_router():
    """Reset the module-level router between tests so singleton tests don't leak."""
    store.reset_router_for_tests(None)
    yield
    store.reset_router_for_tests(None)


# -- JSONL adapter ------------------------------------------------------------


def test_jsonl_append_writes_line_and_returns_row(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox.jsonl"
    router = StorageRouter(specs=(StoreSpec("inbox", "jsonl", inbox, _JsonlAdapter),))

    stored = router.append("inbox", {"text": "hi", "source": "test"})

    assert stored["text"] == "hi"
    assert stored["source"] == "test"
    assert "id" in stored
    written = [json.loads(line) for line in inbox.read_text().splitlines() if line]
    assert written == [stored]


def test_jsonl_append_assigns_uuid_when_id_missing(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox.jsonl"
    router = StorageRouter(specs=(StoreSpec("inbox", "jsonl", inbox, _JsonlAdapter),))

    stored = router.append("inbox", {"text": "x"})

    assert isinstance(stored["id"], str) and len(stored["id"]) > 0


def test_jsonl_append_preserves_caller_id(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox.jsonl"
    router = StorageRouter(specs=(StoreSpec("inbox", "jsonl", inbox, _JsonlAdapter),))

    stored = router.append("inbox", {"id": "caller-id", "text": "x"})

    assert stored["id"] == "caller-id"


def test_jsonl_read_empty_returns_empty_list(tmp_path: Path) -> None:
    router = StorageRouter(specs=(StoreSpec("inbox", "jsonl", tmp_path / "missing.jsonl", _JsonlAdapter),))
    assert router.read("inbox") == []


def test_jsonl_read_corrupt_line_raises_storage_error(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox.jsonl"
    inbox.write_text(
        '{"id":"1","text":"ok"}\n'
        "not json\n"
        '{"id":"2","text":"fine"}\n',
        encoding="utf-8",
    )
    router = StorageRouter(specs=(StoreSpec("inbox", "jsonl", inbox, _JsonlAdapter),))

    with pytest.raises(StorageError) as exc:
        router.read("inbox")

    message = str(exc.value)
    assert exc.value.op == "read"
    assert str(inbox) in message
    assert "line 2" in message


def test_jsonl_read_non_object_line_raises_storage_error(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox.jsonl"
    inbox.write_text('{"id":"1","text":"ok"}\n["not", "object"]\n', encoding="utf-8")
    router = StorageRouter(specs=(StoreSpec("inbox", "jsonl", inbox, _JsonlAdapter),))

    with pytest.raises(StorageError) as exc:
        router.read("inbox")

    assert exc.value.op == "read"
    assert str(inbox) in str(exc.value)
    assert "line 2" in str(exc.value)


def test_jsonl_read_limit_returns_tail(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox.jsonl"
    content = "".join(
        json.dumps({"id": str(i), "text": f"line{i}"}) + "\n" for i in range(5)
    )
    inbox.write_text(content, encoding="utf-8")
    router = StorageRouter(specs=(StoreSpec("inbox", "jsonl", inbox, _JsonlAdapter),))

    rows = router.read("inbox", ReadQuery(limit=2))

    assert [r["text"] for r in rows] == ["line3", "line4"]


def test_jsonl_read_where_filters(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox.jsonl"
    content = "".join(
        json.dumps(entry) + "\n"
        for entry in [
            {"id": "1", "source": "mobile", "text": "a"},
            {"id": "2", "source": "desktop", "text": "b"},
            {"id": "3", "source": "mobile", "text": "c"},
        ]
    )
    inbox.write_text(content, encoding="utf-8")
    router = StorageRouter(specs=(StoreSpec("inbox", "jsonl", inbox, _JsonlAdapter),))

    rows = router.read("inbox", ReadQuery(where={"source": "mobile"}))

    assert [r["text"] for r in rows] == ["a", "c"]


def test_jsonl_upsert_rejected_on_append_only_store(tmp_path: Path) -> None:
    router = StorageRouter(specs=(StoreSpec("inbox", "jsonl", tmp_path / "inbox.jsonl", _JsonlAdapter),))
    with pytest.raises(StorageError) as exc:
        router.upsert("inbox", "key", {"v": 1})
    assert exc.value.op == "upsert"


# -- JSON adapter -------------------------------------------------------------


def test_json_upsert_atomic_write(tmp_path: Path) -> None:
    path = tmp_path / "buddy.json"
    router = StorageRouter(specs=(StoreSpec("buddy", "json", path, _JsonAdapter),))

    router.upsert("buddy", "current", {"mood": "happy"})

    assert json.loads(path.read_text(encoding="utf-8")) == {"current": {"mood": "happy"}}


def test_json_upsert_replaces_existing(tmp_path: Path) -> None:
    path = tmp_path / "buddy.json"
    path.write_text(json.dumps({"current": {"mood": "neutral"}}), encoding="utf-8")
    router = StorageRouter(specs=(StoreSpec("buddy", "json", path, _JsonAdapter),))

    router.upsert("buddy", "current", {"mood": "happy"})

    assert json.loads(path.read_text(encoding="utf-8")) == {"current": {"mood": "happy"}}


def test_json_append_rejected_on_single_record_store(tmp_path: Path) -> None:
    router = StorageRouter(specs=(StoreSpec("buddy", "json", tmp_path / "buddy.json", _JsonAdapter),))
    with pytest.raises(StorageError):
        router.append("buddy", {"v": 1})


def test_json_read_missing_returns_empty(tmp_path: Path) -> None:
    router = StorageRouter(specs=(StoreSpec("buddy", "json", tmp_path / "missing.json", _JsonAdapter),))
    assert router.read("buddy") == []


def test_json_read_corrupt_raises_storage_error(tmp_path: Path) -> None:
    path = tmp_path / "broken.json"
    path.write_text("{not json", encoding="utf-8")
    router = StorageRouter(specs=(StoreSpec("buddy", "json", path, _JsonAdapter),))
    with pytest.raises(StorageError) as exc:
        router.read("buddy")
    assert exc.value.op == "read"
    assert str(path) in str(exc.value)


def test_json_read_invalid_shape_raises_storage_error(tmp_path: Path) -> None:
    path = tmp_path / "bad-shape.json"
    path.write_text(json.dumps("not an object or list"), encoding="utf-8")
    router = StorageRouter(specs=(StoreSpec("buddy", "json", path, _JsonAdapter),))

    with pytest.raises(StorageError) as exc:
        router.read("buddy")

    assert exc.value.op == "read"
    assert str(path) in str(exc.value)


def test_json_upsert_corrupt_existing_raises_storage_error(tmp_path: Path) -> None:
    path = tmp_path / "broken.json"
    path.write_text("{not json", encoding="utf-8")
    router = StorageRouter(specs=(StoreSpec("buddy", "json", path, _JsonAdapter),))

    with pytest.raises(StorageError) as exc:
        router.upsert("buddy", "current", {"mood": "happy"})

    assert exc.value.op == "upsert"
    assert str(path) in str(exc.value)


# -- SQLite adapter (plugin_settings) -----------------------------------------


def test_sqlite_upsert_inserts(tmp_path: Path) -> None:
    db_file = tmp_path / "kitty.db"
    router = StorageRouter(specs=(StoreSpec("plugin_settings", "sqlite", db_file, _PluginSettingsAdapter),))

    router.upsert("plugin_settings", "discord", {"enabled": True})

    with sqlite3.connect(db_file) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT plugin_name, enabled FROM plugin_settings"
        ).fetchone()
    assert row["plugin_name"] == "discord"
    assert bool(row["enabled"]) is True


def test_sqlite_upsert_updates_on_conflict(tmp_path: Path) -> None:
    db_file = tmp_path / "kitty.db"
    router = StorageRouter(specs=(StoreSpec("plugin_settings", "sqlite", db_file, _PluginSettingsAdapter),))

    router.upsert("plugin_settings", "discord", {"enabled": True})
    router.upsert("plugin_settings", "discord", {"enabled": False})

    rows = router.read("plugin_settings")
    assert len(rows) == 1
    assert rows[0] == {"key": "discord", "value": {"enabled": False}}


def test_sqlite_append_rejected_on_keyed_store(tmp_path: Path) -> None:
    db_file = tmp_path / "kitty.db"
    router = StorageRouter(specs=(StoreSpec("plugin_settings", "sqlite", db_file, _PluginSettingsAdapter),))
    with pytest.raises(StorageError):
        router.append("plugin_settings", {"k": "v"})


# -- Router-level concerns ----------------------------------------------------


def test_unknown_store_raises_storage_error() -> None:
    router = StorageRouter(specs=())
    with pytest.raises(StorageError) as exc:
        router.append("nope", {})
    assert exc.value.op == "lookup"
    assert "nope" in str(exc.value)


def test_stores_returns_registry() -> None:
    router = StorageRouter(
        specs=(
            StoreSpec("a", "jsonl", Path("/tmp/a.jsonl"), _JsonlAdapter),
            StoreSpec("b", "sqlite", Path("/tmp/b.db"), _PluginSettingsAdapter),
        )
    )
    names = {s.name for s in router.stores()}
    assert names == {"a", "b"}


def test_default_registry_has_expected_stores() -> None:
    """The default registry wires the stores the first router slice owns."""
    assert {s.name for s in StorageRouter().stores()} == {
        "inbox",
        "token_log",
        "traces",
        "plugin_settings",
    }


# -- Module-level functions use the singleton ---------------------------------


def test_module_level_append_uses_singleton(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox.jsonl"
    store.reset_router_for_tests(
        StorageRouter(specs=(StoreSpec("inbox", "jsonl", inbox, _JsonlAdapter),))
    )

    stored = store.append("inbox", {"text": "hi"})

    assert stored["text"] == "hi"
    assert json.loads(inbox.read_text().strip())["text"] == "hi"


def test_module_level_upsert_uses_singleton(tmp_path: Path) -> None:
    db_file = tmp_path / "kitty.db"
    store.reset_router_for_tests(
        StorageRouter(specs=(StoreSpec("plugin_settings", "sqlite", db_file, _PluginSettingsAdapter),))
    )

    store.upsert("plugin_settings", "telegram", {"enabled": True})

    rows = store.read("plugin_settings")
    assert rows == [{"key": "telegram", "value": {"enabled": True}}]


def test_get_router_returns_singleton(tmp_path: Path) -> None:
    a = store.get_router()
    b = store.get_router()
    assert a is b


def test_reset_router_for_tests_replaces_singleton(tmp_path: Path) -> None:
    custom = StorageRouter(specs=())
    store.reset_router_for_tests(custom)
    assert store.get_router() is custom
