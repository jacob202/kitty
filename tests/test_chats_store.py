"""Tests for chats_store — keyed-by-id chat session CRUD on kitty.db."""
import pytest

from gateway import chats_store


@pytest.fixture(autouse=True)
def isolate_chats_store(monkeypatch, tmp_path):
    """Keep chats tests away from live user data while exercising the Phase C path."""
    phase_b_db = tmp_path / "kitty" / "kitty.db"
    monkeypatch.setattr(chats_store, "CHATS_DB_FILE", phase_b_db, raising=False)


def test_list_chats_empty_when_no_data():
    assert chats_store.list_chats() == []


def test_upsert_then_list_round_trip():
    chat = {"id": "abc", "title": "Hello", "messages": [{"role": "user", "text": "hi"}]}
    chats_store.upsert_chat(chat)

    result = chats_store.list_chats()

    assert result == [chat]


def test_upsert_replaces_existing_chat():
    chats_store.upsert_chat({"id": "abc", "title": "v1"})
    chats_store.upsert_chat({"id": "abc", "title": "v2"})

    result = chats_store.list_chats()

    assert len(result) == 1
    assert result[0]["title"] == "v2"


def test_upsert_requires_id():
    with pytest.raises(ValueError, match="must include 'id'"):
        chats_store.upsert_chat({"title": "no id"})


def test_upsert_preserves_arbitrary_payload_shape():
    chat = {
        "id": "rich",
        "title": "Rich chat",
        "messages": [
            {"role": "user", "text": "hello", "ts": 1234567890},
            {"role": "assistant", "text": "hi", "tool_calls": [{"name": "search"}]},
        ],
        "metadata": {"source": "desktop", "project": "kitty"},
    }
    chats_store.upsert_chat(chat)

    result = chats_store.list_chats()

    assert result[0] == chat


def test_delete_existing_chat_returns_true():
    chats_store.upsert_chat({"id": "abc", "title": "x"})

    deleted = chats_store.delete_chat("abc")

    assert deleted is True
    assert chats_store.list_chats() == []


def test_delete_missing_chat_returns_false():
    deleted = chats_store.delete_chat("never-existed")

    assert deleted is False


def test_list_orders_newest_first():
    chats_store.upsert_chat({"id": "old", "title": "old"})
    chats_store.upsert_chat({"id": "new", "title": "new"})
    chats_store.upsert_chat({"id": "mid", "title": "mid"})

    # Touch "mid" after "new" so mid becomes newest.
    chats_store.upsert_chat({"id": "mid", "title": "mid v2"})

    result = chats_store.list_chats()
    ids = [c["id"] for c in result]

    assert ids == ["mid", "new", "old"]


def test_upsert_supports_unicode_payload():
    chat = {"id": "uni", "title": "こんにちは", "messages": [{"text": "🌙"}]}
    chats_store.upsert_chat(chat)

    result = chats_store.list_chats()

    assert result[0] == chat
