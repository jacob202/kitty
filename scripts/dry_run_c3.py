#!/usr/bin/env python3.12
"""C3-0 dry-run helper for the cron_schedules migration.

Reads every row from the legacy `data/cron_schedules.db:schedules`
table and inserts it into the destination `kitty.db:cron_schedules`
table. Used in C3-0 to verify the migration logic is correct on a
copy of real data BEFORE any live change.

Usage:
    python3.12 scripts/dry_run_c3.py --src /tmp/cron_pre.db --dst /tmp/kitty_pre.db

The script does NOT touch any data outside `--src` and `--dst`. It
exists only for the dry run; discard it after the live migration
lands.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys

SRC_TABLE = "schedules"
DST_TABLE = "cron_schedules"

SRC_COLS = (
    "id",
    "name",
    "action",
    "schedule_type",
    "schedule_value",
    "metadata",
    "enabled",
    "last_run",
    "created_at",
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--src", required=True, help="legacy cron_schedules.db copy")
    parser.add_argument("--dst", required=True, help="kitty.db copy with migration 012 applied")
    args = parser.parse_args()

    src = sqlite3.connect(args.src)
    src.row_factory = sqlite3.Row
    dst = sqlite3.connect(args.dst)

    src_rows = src.execute(f"SELECT {', '.join(SRC_COLS)} FROM {SRC_TABLE}").fetchall()
    print(f"Source: {len(src_rows)} row(s) in {SRC_TABLE}")

    if not src_rows:
        print("Source table is empty — nothing to migrate. Dry run is trivially green.")
        return 0

    placeholders = ", ".join(f":{col}" for col in SRC_COLS)
    insert_sql = (
        f"INSERT OR IGNORE INTO {DST_TABLE} ({', '.join(SRC_COLS)}) "
        f"VALUES ({placeholders})"
    )
    inserted = 0
    for row in src_rows:
        cur = dst.execute(insert_sql, dict(row))
        inserted += cur.rowcount
    dst.commit()

    dst_count = dst.execute(f"SELECT COUNT(*) FROM {DST_TABLE}").fetchone()[0]
    print(f"Destination: {dst_count} row(s) in {DST_TABLE} (inserted {inserted})")

    if dst_count != len(src_rows):
        print(f"MISMATCH: source has {len(src_rows)} rows, destination has {dst_count}", file=sys.stderr)
        return 1

    print("Dry run: counts match. Diff the dumped rows per the plan to confirm column fidelity.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
