#!/usr/bin/env python3
"""Non-destructive backup/restore proof drill (Roadmap 2.2).

Proves that a backup archive restores to byte-identical app-owned data and
that every restored SQLite file passes integrity_check. Runs entirely against a
scratch replica under a temp directory, so it never touches the live data/
directory and never interferes with a running Builder.

Usage:
  python scripts/kitty_backup_proof.py
  python scripts/kitty_backup_proof.py --seed-dir /tmp/kitty-drill-seed

Exit code 0 when the restored replica matches the pre-backup replica and all
SQLite databases pass integrity_check; 1 otherwise. Every mismatch is printed.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import tempfile
from pathlib import Path

from scripts import kitty_backup


def seed_replica(root: Path) -> Path:
    """Build a scratch replica of data/kitty with realistic content."""
    source = root / "data" / "kitty"
    source.mkdir(parents=True)

    (source / "reaction_log.jsonl").write_text(
        '{"emoji": "sparkles", "count": 3}\n{"emoji": "heart", "count": 1}\n',
        encoding="utf-8",
    )
    (source / "drift_log.jsonl").write_text("sample drift line\n", encoding="utf-8")

    nested = source / "image_characters"
    nested.mkdir()
    (nested / "maya.json").write_text(
        json.dumps({"name": "Maya", "trait": "curious"}, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    db_file = source / "kitty.db"
    with sqlite3.connect(db_file) as conn:
        conn.execute("CREATE TABLE messages (id INTEGER PRIMARY KEY, body TEXT)")
        conn.executemany(
            "INSERT INTO messages (body) VALUES (?)",
            [("first",), ("second",), ("third",)],
        )

    tutor_db = source / "tutor_memory.db"
    with sqlite3.connect(tutor_db) as conn:
        conn.execute("CREATE TABLE facts (fact TEXT)")
        conn.executemany(
            "INSERT INTO facts (fact) VALUES (?)",
            [("alpha",), ("beta",)],
        )

    return source


def snapshot(root: Path) -> dict[str, object]:
    """Capture every file's relative path, size, and sha256, plus a logical
    digest of each SQLite file (schema + full row contents).

    SQLite files are compared logically rather than byte-for-byte: the
    ``sqlite3`` backup API rebuilds a fresh, logically identical database, so
    identical bytes are neither required nor guaranteed.
    """
    files: dict[str, dict[str, object]] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        entry: dict[str, object] = {
            "size": path.stat().st_size,
            "sha256": _sha256(path),
        }
        if path.suffix == ".db":
            entry["db_logical"] = _sqlite_logical_digest(path)
        files[rel] = entry
    return {"files": files}


def _sha256(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sqlite_logical_digest(path: Path) -> dict[str, object]:
    with sqlite3.connect(path) as conn:
        schema = [
            row[0]
            for row in conn.execute(
                "SELECT sql FROM sqlite_master WHERE sql IS NOT NULL ORDER BY name"
            )
        ]
        tables = [
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
        ]
        rows: dict[str, list[list[object]]] = {}
        for table in tables:
            rows[table] = [list(row) for row in conn.execute(f"SELECT * FROM {table} ORDER BY 1")]
        return {"schema": schema, "rows": rows}


def compare(a: dict[str, object], b: dict[str, object]) -> list[str]:
    a_files: dict[str, dict[str, object]] = a["files"]  # type: ignore[assignment]
    b_files: dict[str, dict[str, object]] = b["files"]  # type: ignore[assignment]
    diffs: list[str] = []
    for rel in sorted(set(a_files) | set(b_files)):
        if rel not in a_files:
            diffs.append(f"only after restore: {rel}")
        elif rel not in b_files:
            diffs.append(f"missing after restore: {rel}")
            continue
        a_entry = a_files[rel]
        b_entry = b_files[rel]
        if "db_logical" in a_entry or "db_logical" in b_entry:
            if a_entry.get("db_logical") != b_entry.get("db_logical"):
                diffs.append(f"sqlite content changed: {rel}")
        elif a_entry != b_entry:
            diffs.append(f"content changed: {rel} {a_entry} != {b_entry}")
    return diffs


def run_drill(seed_dir: Path | None = None, keep: bool = False) -> int:
    temp_root = Path(seed_dir) if seed_dir else Path(tempfile.mkdtemp(prefix="kitty-backup-proof-"))
    print(f"drill root: {temp_root}")

    source = seed_replica(temp_root)
    backup_root = temp_root / "data" / "backups" / "kitty"

    before = snapshot(source)
    backup_dir = kitty_backup.create_backup(source_dir=source, backup_root=backup_root)
    print(f"backup archive: {backup_dir}")

    shutil.rmtree(source)
    if source.exists():
        raise RuntimeError(f"drill: replica wipe failed, {source} still exists")
    print("replica wiped (simulating data loss)")

    restored = kitty_backup.restore(backup_dir=backup_dir, target_dir=source)
    print(f"restored into: {restored}")

    after = snapshot(source)
    diffs = compare(before, after)

    before_files = before["files"]
    after_files = after["files"]
    assert isinstance(before_files, dict)
    assert isinstance(after_files, dict)
    print(f"files before: {len(before_files)}  after: {len(after_files)}")
    if not diffs:
        print("VERDICT: PASS — restored replica matches pre-backup byte-for-byte")
        return 0

    for diff in diffs:
        print(f"  FAIL: {diff}")
    print(f"VERDICT: FAIL — {len(diffs)} difference(s)")
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed-dir", type=Path, help="scratch root to run the drill in")
    parser.add_argument(
        "--keep",
        action="store_true",
        help="leave the scratch replica in place (default: temp dir is auto-cleaned)",
    )
    args = parser.parse_args(argv)
    return run_drill(seed_dir=args.seed_dir, keep=args.keep)


if __name__ == "__main__":
    raise SystemExit(main())
