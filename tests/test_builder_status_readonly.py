from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

import pytest

from gateway import builder_attempt as ba
from gateway import builder_initiative as bi
from gateway.builder_status_readonly import (
    build_status_snapshot_readonly,
    get_attempt_validation_index_readonly,
    get_initiative_readonly,
)


def _manifest() -> dict:
    return {
        "manifest_version": 1,
        "initiative_id": "readonly-proof",
        "title": "Read-only proof",
        "description": "Prove status reads do not mutate Builder state.",
        "packets": [
            {
                "id": "packet-1",
                "title": "Inspect",
                "objective": "Read durable state",
                "depends_on": [],
                "acceptance_criteria": ["status is visible"],
                "allowed_paths": ["gateway/"],
                "validation_commands": [],
            }
        ],
    }


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _schema_version(path: Path) -> int:
    conn = sqlite3.connect(path)
    try:
        return int(conn.execute("PRAGMA schema_version").fetchone()[0])
    finally:
        conn.close()


def test_readonly_snapshot_does_not_create_missing_database(tmp_path: Path) -> None:
    db_path = tmp_path / "missing.db"

    with pytest.raises(FileNotFoundError):
        build_status_snapshot_readonly(db_path=db_path)

    assert not db_path.exists()


def test_readonly_snapshot_leaves_existing_database_bytes_and_schema_unchanged(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "builder.db"
    ba.init_db(db_path)
    monkeypatch.setattr(bi, "resolve_base_sha", lambda _root=None: "a" * 40)
    bi.apply_manifest(_manifest(), db_path=db_path, repo_root=tmp_path)

    before_digest = _digest(db_path)
    before_schema = _schema_version(db_path)

    snapshot = build_status_snapshot_readonly(db_path=db_path)

    assert snapshot["schema_version"] >= 1
    assert snapshot["initiatives"][0]["initiative_id"] == "readonly-proof"
    assert snapshot["initiatives"][0]["packets"][0]["task_state"] == "queued"
    assert _schema_version(db_path) == before_schema
    assert _digest(db_path) == before_digest


def test_readonly_initiative_lookup_returns_manifest_without_mutating_db(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "builder.db"
    ba.init_db(db_path)
    monkeypatch.setattr(bi, "resolve_base_sha", lambda _root=None: "a" * 40)
    bi.apply_manifest(_manifest(), db_path=db_path, repo_root=tmp_path)
    before = _digest(db_path)

    initiative = get_initiative_readonly("readonly-proof", db_path=db_path)

    assert initiative is not None
    assert initiative["manifest"] == _manifest()
    assert initiative["packets"][0]["packet_id"] == "packet-1"
    assert _digest(db_path) == before



def test_attempt_validation_index_is_strict_and_non_mutating(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "builder.db"
    manifest = _manifest()
    manifest["packets"][0]["validation_commands"] = [
        "printf 'TOPSECRET /private/unsafe/path\\n'"
    ]
    ba.init_db(db_path)
    monkeypatch.setattr(bi, "resolve_base_sha", lambda _root=None: "a" * 40)
    bi.apply_manifest(manifest, db_path=db_path, repo_root=tmp_path)
    attempt = ba.start_attempt("readonly-proof", "packet-1", db_path=db_path)
    ba.run_validation(attempt["id"], cwd=tmp_path, db_path=db_path)
    before = _digest(db_path)

    proof = get_attempt_validation_index_readonly(attempt["id"], db_path=db_path)

    assert proof is not None
    assert proof["attempt_id"] == attempt["id"]
    assert proof["validation_status"] == "passed"
    assert proof["commands"][0]["passed"] is True
    assert len(proof["commands"][0]["command_sha256"]) == 64
    assert "command" not in proof["commands"][0]
    assert "output_tail" not in str(proof)
    assert "TOPSECRET" not in str(proof)
    assert "/private/unsafe/path" not in str(proof)
    assert _digest(db_path) == before


def test_attempt_validation_index_does_not_create_missing_database(tmp_path: Path) -> None:
    db_path = tmp_path / "missing.db"

    with pytest.raises(FileNotFoundError):
        get_attempt_validation_index_readonly(1, db_path=db_path)

    assert not db_path.exists()
