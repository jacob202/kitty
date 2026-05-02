#!/usr/bin/env python3
"""
Build one plain-text voice corpus for Kitty from:
  - iMessage: outbound-only rows from ~/Library/Messages/chat.db (is_from_me = 1, text column).
  - Gmail Sent: one or more Takeout .mbox files (plain bodies; strips lines starting with '>').

Outputs UTF-8 text suitable for retrieval / indexing — not for committing (personal data).

Examples:
  python3 scripts/build_voice_corpus.py --out data/voice_corpus/jacob_voice.txt
  python3 scripts/build_voice_corpus.py --mbox ~/Downloads/Takeout/Mail/Sent.mbox \\
      --since 2022-01-01 --out data/voice_corpus/jacob_voice.txt

Terminal needs Full Disk Access to read chat.db (System Settings → Privacy & Security → Full Disk Access).
Messages stored only in attributedBody (common on newer macOS) are skipped with a count; re-export with
imessage-exporter to HTML/txt and merge later, or we can extend this script.
"""
from __future__ import annotations

import argparse
import email
import mailbox
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

# macOS iMessage: nanoseconds since 2001-01-01 00:00:00 UTC
_APPLE_2001 = datetime(2001, 1, 1, tzinfo=timezone.utc).timestamp()


def _apple_time_to_unix(value: int | float | None) -> float | None:
    if value is None:
        return None
    v = float(value)
    if v > 1e12:  # treat as ns
        return _APPLE_2001 + v / 1e9
    if v > 1e9:  # already seconds since 2001? rare
        return _APPLE_2001 + v
    return v  # assume unix seconds


def _parse_since(s: str) -> float:
    dt = datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return dt.timestamp()


def _iter_imessage_outbound(
    db_path: Path, since_unix: float | None
) -> tuple[list[str], int, int]:
    """
    Returns (lines of text, used_count, skipped_no_text).
    """
    used: list[str] = []
    skipped = 0
    uri = f"file:{db_path.resolve().as_posix()}?mode=ro"
    try:
        con = sqlite3.connect(uri, uri=True)
    except sqlite3.OperationalError as e:
        print(
            f"Cannot open {db_path}: {e}\n"
            "→ Grant Full Disk Access to Terminal (or iTerm) in\n"
            "  System Settings → Privacy & Security → Full Disk Access",
            file=sys.stderr,
        )
        raise SystemExit(1) from e
    con.row_factory = sqlite3.Row
    try:
        cur = con.execute(
            """
            SELECT text, date
            FROM message
            WHERE is_from_me = 1
            """
        )
        for row in cur:
            text = row["text"]
            if text is None or not str(text).strip():
                skipped += 1
                continue
            ts = _apple_time_to_unix(row["date"])
            if since_unix is not None and ts is not None and ts < since_unix:
                continue
            used.append(str(text).strip())
    finally:
        con.close()
    return used, len(used), skipped


def _strip_quoted_email_lines(body: str) -> str:
    out: list[str] = []
    for line in body.splitlines():
        s = line.strip()
        if s.startswith(">"):
            continue
        if re.match(r"^On .+ wrote:$", s):
            continue
        out.append(line)
    return "\n".join(out).strip()


def _decode_mime_part(part) -> str:
    try:
        payload = part.get_payload(decode=True)
        if payload is None:
            return ""
        charset = part.get_content_charset() or "utf-8"
        return payload.decode(charset, errors="replace")
    except (LookupError, UnicodeError, AttributeError):
        return ""


def _iter_mbox_sent(mbox_path: Path) -> list[str]:
    if not mbox_path.is_file():
        print(f"MBOX not found: {mbox_path}", file=sys.stderr)
        raise SystemExit(1)
    texts: list[str] = []
    mbox_obj = mailbox.mbox(mbox_path)
    for msg in mbox_obj:
        if isinstance(msg, email.message.Message):
            body_text = ""
            if msg.is_multipart():
                for part in msg.walk():
                    ctype = part.get_content_type()
                    if ctype == "text/plain" and not part.get_filename():
                        body_text += _decode_mime_part(part) + "\n"
            else:
                body_text = _decode_mime_part(msg)
            cleaned = _strip_quoted_email_lines(body_text)
            if cleaned:
                texts.append(cleaned.strip())
    return texts


def main() -> None:
    p = argparse.ArgumentParser(description="Build Jacob voice corpus (iMessage + Gmail MBOX).")
    p.add_argument(
        "--chat-db",
        type=Path,
        default=Path.home() / "Library" / "Messages" / "chat.db",
        help="Path to iMessage chat.db",
    )
    p.add_argument(
        "--mbox",
        type=Path,
        action="append",
        default=[],
        metavar="PATH",
        help="Gmail Takeout .mbox (repeat for multiple files)",
    )
    p.add_argument(
        "--since",
        type=str,
        default=None,
        help="Only iMessage on/after this date (YYYY-MM-DD), UTC",
    )
    p.add_argument(
        "--out",
        type=Path,
        default=Path("data/voice_corpus/jacob_voice.txt"),
        help="Output file (UTF-8 text)",
    )
    p.add_argument(
        "--skip-imessage",
        action="store_true",
        help="Only process MBOX files (e.g. chat.db not accessible)",
    )
    args = p.parse_args()

    since_unix = _parse_since(args.since) if args.since else None

    chunks: list[str] = []
    im_used = im_skip = 0

    if not args.skip_imessage:
        if not args.chat_db.is_file():
            print(
                f"iMessage database not found at {args.chat_db}\n"
                "→ Use --skip-imessage if you only have Gmail MBOX for now.",
                file=sys.stderr,
            )
            raise SystemExit(1)
        lines, im_used, im_skip = _iter_imessage_outbound(args.chat_db, since_unix)
        if lines:
            chunks.append("=== iMessage (outbound text column only) ===\n")
            chunks.extend(lines)
            chunks.append("")

    for mbox in args.mbox:
        parts = _iter_mbox_sent(mbox)
        if parts:
            chunks.append(f"=== Gmail MBOX: {mbox.name} ===\n")
            chunks.extend(parts)
            chunks.append("")

    body = "\n".join(chunks).strip()
    if not body:
        print("Nothing to write — check chat.db access, date filter, or MBOX paths.", file=sys.stderr)
        raise SystemExit(2)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(body + "\n", encoding="utf-8")

    print(f"Wrote {args.out} ({len(body)} characters)")
    if not args.skip_imessage:
        print(
            f"iMessage: {im_used} messages included, {im_skip} outbound rows skipped "
            "(empty text / attributedBody-only — normal on newer macOS)."
        )


if __name__ == "__main__":
    main()
