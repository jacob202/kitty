#!/usr/bin/env python3.12
"""CLI for the JSON import/export of Phase B storage stores.

Usage:
    python3.12 scripts/storage_io.py export [path]
    python3.12 scripts/storage_io.py import <path>

Default path is data/kitty-storage-export.json. Exports include the
plugin_settings and todos stores. Imports replace those stores
transactionally (the whole import either succeeds or raises).
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# path-insert above must precede this import; scripts/ lives below repo root
from gateway import storage_sync  # noqa: E402

logger = logging.getLogger(__name__)
# Idempotent basicConfig: do not overwrite if the caller already
# wired logs (e.g. a future pytest or --log-level invocation).
if not logging.getLogger().handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[1] in {"-h", "--help"}:
        logger.info(__doc__)
        return 0

    cmd = argv[1]
    if cmd == "export":
        path = Path(argv[2]) if len(argv) > 2 else None
        written = storage_sync.export_to_file(path)
        snapshot = json.loads(written.read_text(encoding="utf-8"))
        counts = {
            k: len(v) if isinstance(v, (list, dict)) else 0 for k, v in snapshot["stores"].items()
        }
        logger.info(f"exported → {written}")
        logger.info(f"  format_version: {snapshot['format_version']}")
        logger.info(f"  exported_at:    {snapshot['exported_at']}")
        for store, count in counts.items():
            logger.info(f"  {store}: {count} record(s)")
        return 0

    if cmd == "import":
        if len(argv) < 3:
            logger.info("usage: storage_io.py import <path>", file=sys.stderr)
            return 2
        path = Path(argv[2])
        try:
            counts = storage_sync.import_from_file(path)
        except (ValueError, FileNotFoundError) as exc:
            logger.error(f"import failed: {exc}", file=sys.stderr)
            return 1
        logger.info(f"imported ← {path}")
        for store, count in counts.items():
            logger.info(f"  {store}: {count} record(s)")
        return 0

    logger.warning(f"unknown command: {cmd!r}. use 'export' or 'import'.", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
