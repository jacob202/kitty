from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

import pytest

from gateway import builder_attempt as ba
from gateway import builder_initiative as bi
from gateway.builder_status_readonly import build_status_snapshot_readonly


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
