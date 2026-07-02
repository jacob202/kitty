"""Tests for signal_store — the append table for connector/system events (P1)."""
import pytest

from gateway import signal_store


@pytest.fixture(autouse=True)
def isolate_signal_store(monkeypatch, tmp_path):
    """Keep signal tests away from live user data."""
    db_file = tmp_path / "kitty" / "kitty.db"
    monkeypatch.setattr(signal_store, "SIGNALS_DB_FILE", db_file, raising=False)


def test_emit_returns_stored_record():
    record = signal_store.emit(
        source="mail", kind="message.received", payload={"subject": "hi"}
    )

    assert record is not None
    assert record["source"] == "mail"
    assert record["kind"] == "message.received"
    assert record["payload"] == {"subject": "hi"}
    assert isinstance(record["id"], int)
    assert record["processed_at"] is None


def test_emit_requires_source_and_kind():
    with pytest.raises(ValueError):
        signal_store.emit(source="", kind="x")
    with pytest.raises(ValueError):
        signal_store.emit(source="mail", kind="  ")


def test_emit_rejects_oversized_payload():
    with pytest.raises(ValueError, match="pointer"):
        signal_store.emit(
            source="mail",
            kind="message.received",
            payload={"body": "x" * (signal_store.MAX_PAYLOAD_BYTES + 1)},
        )


def test_dedupe_key_makes_second_emit_a_noop():
    first = signal_store.emit(source="gh", kind="pr.check", dedupe_key="pr-61-run-9")
    second = signal_store.emit(source="gh", kind="pr.check", dedupe_key="pr-61-run-9")

    assert first is not None
    assert second is None
    assert len(signal_store.list_recent()) == 1


def test_null_dedupe_keys_do_not_collide():
    assert signal_store.emit(source="internal", kind="nudge") is not None
    assert signal_store.emit(source="internal", kind="nudge") is not None
    assert len(signal_store.list_recent()) == 2


def test_list_recent_newest_first_and_source_filter():
    signal_store.emit(source="mail", kind="a", ts=1.0)
    signal_store.emit(source="gh", kind="b", ts=2.0)
    signal_store.emit(source="mail", kind="c", ts=3.0)

    recent = signal_store.list_recent()
    assert [s["kind"] for s in recent] == ["c", "b", "a"]

    mail_only = signal_store.list_recent(source="mail")
    assert [s["kind"] for s in mail_only] == ["c", "a"]


def test_list_since_is_strictly_after():
    signal_store.emit(source="mail", kind="old", ts=10.0)
    signal_store.emit(source="mail", kind="new", ts=20.0)

    assert [s["kind"] for s in signal_store.list_since(ts=10.0)] == ["new"]
    assert signal_store.list_since(ts=20.0) == []


def test_mark_processed_flow():
    record = signal_store.emit(source="mail", kind="message.received")
    assert record is not None
    assert signal_store.count_unprocessed() == 1

    assert signal_store.mark_processed(record["id"]) is True
    assert signal_store.count_unprocessed() == 0
    assert signal_store.list_unprocessed() == []

    # Second mark is a no-op, missing id is a no-op — both report False.
    assert signal_store.mark_processed(record["id"]) is False
    assert signal_store.mark_processed(9999) is False


def test_payload_round_trips_nested_dict():
    payload = {"pr": 61, "checks": {"lint": "green"}}
    signal_store.emit(source="gh", kind="pr.check", payload=payload)

    assert signal_store.list_recent()[0]["payload"] == payload
