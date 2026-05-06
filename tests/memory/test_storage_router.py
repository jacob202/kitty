from __future__ import annotations

import pytest

from src.memory.storage_router import StorageRouter


class FakeSourceLedger:
    def __init__(self):
        self.calls = []

    def quarantine_candidate(self, **kwargs):
        self.calls.append(("quarantine", kwargs))
        return {"id": kwargs["candidate_id"], "state": "quarantined"}

    def promote_candidate(self, **kwargs):
        self.calls.append(("promote", kwargs))
        return {"id": kwargs["candidate_id"], "state": "durable"}

    def retire_candidate(self, **kwargs):
        self.calls.append(("retire", kwargs))
        return {"id": kwargs["candidate_id"], "state": "retired"}


def test_blocks_wrong_store_writes_and_records_event():
    router = StorageRouter(source_ledger=FakeSourceLedger())

    with pytest.raises(ValueError, match="wrong-store write blocked"):
        router.ingest(
            data_kind="knowledge",
            target_store="journaldb",
            writer=lambda **_: "never-called",
        )

    event = router.events()[-1]
    assert event.operation == "ingest"
    assert event.status == "blocked"
    assert event.requested_store == "journaldb"
    assert event.selected_store == "lightrag"


def test_routes_expected_store_write_and_records_success():
    router = StorageRouter(source_ledger=FakeSourceLedger())
    observed = {}

    def writer(**kwargs):
        observed.update(kwargs)
        return {"stored": True}

    result = router.ingest(
        data_kind="knowledge",
        target_store="lightrag",
        writer=writer,
        payload="doc-content",
        domain="general",
    )

    assert result == {"stored": True}
    assert observed["payload"] == "doc-content"
    assert observed["domain"] == "general"
    event = router.events()[-1]
    assert event.status == "routed"
    assert event.selected_store == "lightrag"


def test_candidate_lifecycle_routes_through_source_ledger():
    fake = FakeSourceLedger()
    router = StorageRouter(source_ledger=fake)

    quarantined = router.quarantine_candidate(candidate_id=7, reason="conflict")
    promoted = router.promote_candidate(candidate_id=7, confidence=0.91)
    retired = router.retire_candidate(candidate_id=7)

    assert quarantined["state"] == "quarantined"
    assert promoted["state"] == "durable"
    assert retired["state"] == "retired"
    assert [name for name, _ in fake.calls] == ["quarantine", "promote", "retire"]
    assert [event.operation for event in router.events()[-3:]] == ["quarantine", "promote", "retire"]
