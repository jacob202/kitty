"""Watch iCloud inbox for voice notes and ingest them into data/inbox.jsonl."""

from __future__ import annotations

import logging
from pathlib import Path

from gateway import desktop_store
from gateway.paths import INBOX_FILE

logger = logging.getLogger("kitty.inbox_watcher")

ICLOUD_INBOX = Path.home() / "Library/Mobile Documents/com~apple~CloudDocs/inbox"

def _ingest(md_file: Path) -> None:
    text = md_file.read_text(encoding="utf-8").strip()
    if not text:
        md_file.unlink(missing_ok=True)
        return
    entry = desktop_store.make_inbox_entry(
        text=text,
        source="icloud-inbox",
        capture_type="voice_note",
    )
    entry["id"] = md_file.stem
    desktop_store.append_inbox_entry(entry, inbox_file=INBOX_FILE)
    md_file.unlink(missing_ok=True)
    logger.info("inbox: ingested %s (%d chars)", md_file.name, len(text))


def scan_once() -> None:
    """Scan the inbox once. Retries each file once, then raises loudly."""
    for md_file in sorted(ICLOUD_INBOX.glob("*.md")):
        try:
            _ingest(md_file)
        except Exception as exc:
            logger.warning("inbox: failed to ingest %s: %s; retrying once", md_file.name, exc)
            try:
                _ingest(md_file)
            except Exception as retry_exc:
                raise RuntimeError(
                    f"inbox: failed to ingest {md_file.name} after retry: {retry_exc}"
                ) from retry_exc
