"""Watch iCloud inbox for voice notes and ingest them into data/inbox.jsonl."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from gateway.paths import DATA_DIR

logger = logging.getLogger("kitty.inbox_watcher")

ICLOUD_INBOX = Path.home() / "Library/Mobile Documents/com~apple~CloudDocs/inbox"
INBOX_JSONL = DATA_DIR / "inbox.jsonl"
POLL_INTERVAL = 30  # seconds


def _ingest(md_file: Path) -> None:
    text = md_file.read_text(encoding="utf-8").strip()
    if not text:
        md_file.unlink(missing_ok=True)
        return
    entry = {
        "id": md_file.stem,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": "icloud-inbox",
        "text": text,
    }
    INBOX_JSONL.parent.mkdir(parents=True, exist_ok=True)
    with INBOX_JSONL.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    md_file.unlink(missing_ok=True)
    logger.info("inbox: ingested %s (%d chars)", md_file.name, len(text))


async def watch_loop() -> None:
    """Poll iCloud inbox every POLL_INTERVAL seconds."""
    if not ICLOUD_INBOX.exists():
        logger.warning("inbox_watcher: iCloud inbox not found at %s — skipping", ICLOUD_INBOX)
        return
    logger.info("inbox_watcher: watching %s", ICLOUD_INBOX)
    while True:
        try:
            for md_file in sorted(ICLOUD_INBOX.glob("*.md")):
                try:
                    _ingest(md_file)
                except Exception as e:
                    logger.warning("inbox: failed to ingest %s: %s", md_file.name, e)
        except Exception as e:
            logger.warning("inbox_watcher: poll error: %s", e)
        await asyncio.sleep(POLL_INTERVAL)
