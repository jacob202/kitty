"""Tests for triage — inbox classification into action buckets (P2)."""
import json
from types import SimpleNamespace

import pytest

from gateway import desktop_store, triage


@pytest.fixture(autouse=True)
def isolate(monkeypatch, tmp_path):
    """Point triage at a temp kitty.db and a temp inbox, away from live data."""
    db_file = tmp_path / "kitty" / "kitty.db"
    inbox_file = tmp_path / "inbox.jsonl"
    monkeypatch.setattr(triage, "TRIAGE_DB_FILE", db_file, raising=False)
    # read_inbox binds INBOX_FILE as a default at def time, so patching the
    # module constant is not enough — rebind the function to the temp inbox.
    real_read = desktop_store.read_inbox
    monkeypatch.setattr(
        desktop_store,
        "read_inbox",
        lambda limit=20, inbox_file=inbox_file: real_read(limit=limit, inbox_file=inbox_file),
    )
    return SimpleNamespace(db_file=db_file, inbox_file=inbox_file)


def _capture(isolate, text):
    return desktop_store.append_text_capture(text=text, inbox_file=isolate.inbox_file)


def _stub(bucket, confidence=0.9, rationale="because"):
    return lambda prompt: json.dumps(
        {"bucket": bucket, "confidence": confidence, "rationale": rationale}
    )


@pytest.mark.parametrize("bucket", triage.BUCKETS)
def test_classifies_into_each_bucket(isolate, bucket):
    _capture(isolate, f"note for {bucket}")

    result = triage.run_pass(llm_fn=_stub(bucket))

    assert result == {"processed": 1, "counts": {**{b: 0 for b in triage.BUCKETS}, bucket: 1}}
    rows = triage.list_triaged(bucket=bucket)
    assert len(rows) == 1
    assert rows[0]["bucket"] == bucket
    assert rows[0]["text"] == f"note for {bucket}"


def test_low_confidence_reroutes_to_needs_jacob(isolate):
    _capture(isolate, "ambiguous thing")

    result = triage.run_pass(llm_fn=_stub("now", confidence=0.3, rationale="unsure"))

    assert result["counts"]["needs_jacob"] == 1
    assert result["counts"]["now"] == 0
    row = triage.list_triaged()[0]
    assert row["bucket"] == "needs_jacob"
    assert "rerouted" in row["rationale"]


def test_low_confidence_needs_jacob_is_not_double_wrapped(isolate):
    _capture(isolate, "already ambiguous")

    triage.run_pass(llm_fn=_stub("needs_jacob", confidence=0.2, rationale="hand to jacob"))

    row = triage.list_triaged()[0]
    assert row["bucket"] == "needs_jacob"
    assert row["rationale"] == "hand to jacob"


def test_empty_model_output_raises_and_writes_nothing(isolate):
    _capture(isolate, "x")

    with pytest.raises(triage.TriageError):
        triage.run_pass(llm_fn=lambda prompt: "")

    assert triage.list_triaged() == []


def test_unparseable_output_raises_and_writes_nothing(isolate):
    _capture(isolate, "x")

    with pytest.raises(triage.TriageError):
        triage.run_pass(llm_fn=lambda prompt: "not json at all")

    assert triage.list_triaged() == []


def test_unknown_bucket_raises_and_writes_nothing(isolate):
    _capture(isolate, "x")

    with pytest.raises(triage.TriageError):
        triage.run_pass(llm_fn=_stub("maybe_later"))

    assert triage.list_triaged() == []


def test_non_numeric_confidence_raises(isolate):
    _capture(isolate, "x")

    def stub(prompt):
        return json.dumps({"bucket": "now", "confidence": "high", "rationale": "r"})

    with pytest.raises(triage.TriageError):
        triage.run_pass(llm_fn=stub)

    assert triage.list_triaged() == []


def test_drop_is_a_row_and_inbox_is_byte_identical(isolate):
    _capture(isolate, "pure noise")
    before = isolate.inbox_file.read_bytes()

    triage.run_pass(llm_fn=_stub("drop", confidence=0.95, rationale="noise"))

    assert isolate.inbox_file.read_bytes() == before
    dropped = triage.list_triaged(bucket="drop")
    assert len(dropped) == 1
    assert dropped[0]["text"] == "pure noise"


def test_second_pass_skips_already_triaged(isolate):
    _capture(isolate, "one")
    calls = {"n": 0}

    def stub(prompt):
        calls["n"] += 1
        return json.dumps({"bucket": "someday", "confidence": 0.8, "rationale": "r"})

    first = triage.run_pass(llm_fn=stub)
    second = triage.run_pass(llm_fn=stub)

    assert first["processed"] == 1
    assert second["processed"] == 0
    assert calls["n"] == 1  # the model is not consulted again for a triaged id
    assert len(triage.list_triaged()) == 1


def test_limit_caps_entries_and_leaves_rest_for_next_pass(isolate):
    for i in range(3):
        _capture(isolate, f"note {i}")
    stub = _stub("someday", confidence=0.8)

    assert triage.run_pass(limit=2, llm_fn=stub)["processed"] == 2
    assert triage.run_pass(limit=2, llm_fn=stub)["processed"] == 1
    assert triage.run_pass(limit=2, llm_fn=stub)["processed"] == 0


def test_fenced_json_output_is_parsed(isolate):
    _capture(isolate, "x")
    fenced = '```json\n{"bucket": "reference", "confidence": 0.9, "rationale": "r"}\n```'

    result = triage.run_pass(llm_fn=lambda prompt: fenced)

    assert result["counts"]["reference"] == 1
