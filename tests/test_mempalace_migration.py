"""Tests for the mem0 -> MemPalace migration logic.

These exercise the pure, side-effect-free core (normalization, dry-run safety,
idempotency/resume, per-item failure isolation, manifest round-trip) with the
ingest call injected — so they run in CI WITHOUT the `mempalace` package.
"""
import importlib.util
import json
from pathlib import Path

import pytest

# Load the script module by path (scripts/ is not an importable package).
_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "migrate_mem0_to_mempalace.py"
_spec = importlib.util.spec_from_file_location("migrate_mem0_to_mempalace", _SCRIPT)
mig = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mig)


# --- normalize_memory ---


def test_normalize_extracts_text_and_namespace():
    item = mig.normalize_memory(
        {"id": "m1", "memory": " likes tea ", "metadata": {"namespace": "facts"}}
    )
    assert item == {"id": "m1", "text": "likes tea", "namespace": "facts",
                    "metadata": {"namespace": "facts"}}


def test_normalize_falls_back_to_content_hash_id():
    item = mig.normalize_memory({"text": "no id here"})
    assert item["id"].startswith("sha1:")
    # Stable: same text -> same id (drives idempotency even without mem0 ids).
    assert item["id"] == mig.normalize_memory({"text": "no id here"})["id"]


@pytest.mark.parametrize("raw", [{}, {"memory": "   "}, "not a dict", None])
def test_normalize_rejects_empty_or_nondict(raw):
    assert mig.normalize_memory(raw) is None


# --- migrate(): dry-run safety ---


def test_dry_run_writes_nothing_and_counts():
    def boom(_t, _m):
        raise AssertionError("ingest must never run during dry-run")

    manifest = {"migrated_ids": []}
    summary = mig.migrate(
        [{"id": "a", "memory": "x"}, {"id": "b", "memory": "y"}, {"memory": ""}],
        boom, manifest, dry_run=True, log=lambda _m: None,
    )
    assert summary["would_migrate"] == 2
    assert summary["empty"] == 1
    assert summary["migrated"] == 0
    assert manifest["migrated_ids"] == []  # untouched


# --- migrate(): execute path ---


def test_execute_ingests_and_records_ids():
    sent = []
    manifest = {"migrated_ids": []}
    summary = mig.migrate(
        [{"id": "a", "memory": "fact one"}, {"id": "b", "memory": "fact two"}],
        lambda t, m: sent.append(t), manifest, dry_run=False, log=lambda _m: None,
    )
    assert [s for s in sent] == ["fact one", "fact two"]
    assert summary["migrated"] == 2
    assert manifest["migrated_ids"] == ["a", "b"]


def test_idempotent_resume_skips_already_migrated():
    sent = []
    manifest = {"migrated_ids": ["a"]}  # 'a' done in a prior (interrupted) run
    summary = mig.migrate(
        [{"id": "a", "memory": "one"}, {"id": "b", "memory": "two"}],
        lambda t, m: sent.append(t), manifest, dry_run=False, log=lambda _m: None,
    )
    assert sent == ["two"]
    assert summary["skipped"] == 1 and summary["migrated"] == 1
    assert manifest["migrated_ids"] == ["a", "b"]


def test_one_failed_item_does_not_abort_run():
    def flaky(text, _m):
        if "bad" in text:
            raise RuntimeError("ingest blew up")

    manifest = {"migrated_ids": []}
    summary = mig.migrate(
        [{"id": "a", "memory": "good"}, {"id": "b", "memory": "bad"},
         {"id": "c", "memory": "good2"}],
        flaky, manifest, dry_run=False, log=lambda _m: None,
    )
    assert summary["migrated"] == 2 and summary["failed"] == 1
    assert manifest["migrated_ids"] == ["a", "c"]  # the failed id is NOT recorded


# --- manifest round-trip ---


def test_manifest_load_save_roundtrip(tmp_path):
    path = tmp_path / "state.json"
    assert mig.load_manifest(path) == {"migrated_ids": [], "runs": []}  # missing -> default
    mig.save_manifest(path, {"migrated_ids": ["x", "y"], "runs": []})
    assert json.loads(path.read_text())["migrated_ids"] == ["x", "y"]


def test_load_manifest_tolerates_corrupt_file(tmp_path):
    path = tmp_path / "state.json"
    path.write_text("{ not json")
    assert mig.load_manifest(path) == {"migrated_ids": [], "runs": []}
