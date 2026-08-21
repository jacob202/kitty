#!/usr/bin/env python3
"""Remove artifact rows left behind by tests that once wrote to the live store.

Capture tests used to run against the canonical ``kitty.db`` instead of a
temporary one, so the artifacts table accumulated rows pointing at pytest
temp directories that no longer exist. The leak is closed; this clears the
residue.

Only rows that are BOTH pytest-pathed AND missing from disk are removed, so a
real artifact can never be caught by it. Writes a timestamped database backup
first, and prints what it would do unless ``--apply`` is passed.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sqlite3
import time
from pathlib import Path

from gateway.paths import KITTY_DB_FILE


def dead_test_rows(conn: sqlite3.Connection) -> list[tuple[str, str]]:
    rows = conn.execute("SELECT id, storage_uri FROM artifacts").fetchall()
    return [
        (row[0], row[1] or "")
        for row in rows
        if row[1] and "pytest" in row[1] and not os.path.exists(row[1])
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="actually delete the rows")
    args = parser.parse_args()

    db_path = Path(KITTY_DB_FILE)
    with sqlite3.connect(db_path) as conn:
        doomed = dead_test_rows(conn)
        total = conn.execute("SELECT COUNT(*) FROM artifacts").fetchone()[0]

    print(f"{db_path}: {total} artifact row(s), {len(doomed)} dead test row(s)")
    if not doomed:
        return
    if not args.apply:
        for artifact_id, uri in doomed[:5]:
            print(f"  would remove {artifact_id}  {uri}")
        if len(doomed) > 5:
            print(f"  … and {len(doomed) - 5} more")
        print("re-run with --apply to remove them")
        return

    backup = db_path.with_name(f"{db_path.name}.bak-{time.strftime('%Y%m%d-%H%M%S')}")
    shutil.copy2(db_path, backup)
    with sqlite3.connect(db_path) as conn:
        conn.executemany(
            "DELETE FROM artifacts WHERE id = ?", [(artifact_id,) for artifact_id, _ in doomed]
        )
        conn.commit()
        remaining = conn.execute("SELECT COUNT(*) FROM artifacts").fetchone()[0]
    print(f"backup written to {backup}")
    print(f"removed {len(doomed)} row(s); {remaining} remain")


if __name__ == "__main__":
    main()
