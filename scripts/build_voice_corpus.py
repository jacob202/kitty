#!/usr/bin/env python3
"""
Build one plain-text voice corpus for Kitty from:
  - iMessage: outbound-only rows from ~/Library/Messages/chat.db (is_from_me = 1, text column), and/or
  - iMessage: ``Me`` message bodies from ``imessage-exporter -f txt`` output (see --imessage-export-dir), and/or
  - Gmail Sent: one or more Takeout .mbox files (plain bodies; strips lines starting with '>').

Outputs UTF-8 text suitable for retrieval / indexing — not for committing (personal data).

Examples:
  python3 scripts/build_voice_corpus.py --out data/voice_corpus/jacob_voice.txt
  python3 scripts/build_voice_corpus.py --mbox ~/Downloads/Takeout/Mail/Sent.mbox \\
      --since 2022-01-01 --out data/voice_corpus/jacob_voice.txt
  python3 scripts/build_voice_corpus.py --skip-imessage \\
      --imessage-export-dir data/voice_corpus/imessage_export_full \\
      --mbox ~/Downloads/Takeout/Mail/Sent.mbox --out data/voice_corpus/jacob_voice.txt

Terminal needs Full Disk Access to read chat.db (System Settings → Privacy & Security → Full Disk Access).
Messages stored only in attributedBody (common on newer macOS) are skipped with a count unless you use
``imessage-exporter`` + ``--imessage-export-dir``.
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

# imessage-exporter txt: "Mon DD, YYYY …" at start of stripped line
_EXPORTER_TS = re.compile(r"^[A-Z][a-z]{2} \d{1,2}, \d{4}")

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


def _extract_me_bodies_from_exporter_text(text: str, sender_label: str = "Me") -> list[str]:
    """
    Parse imessage-exporter ``-f txt`` format: timestamp line, sender line, body lines;
    next message starts with a timestamp at the same or smaller indent (handles nested threads).
    """
    label = sender_label.strip()
    lines = text.replace("\r\n", "\n").splitlines()
    bodies: list[str] = []
    i, n = 0, len(lines)
    while i < n:
        st = lines[i].strip()
        if not _EXPORTER_TS.match(st):
            i += 1
            continue
        indent = len(lines[i]) - len(lines[i].lstrip(" "))
        i += 1
        if i >= n:
            break
        if lines[i].strip() != label:
            while i < n:
                ls = lines[i]
                st2 = ls.strip()
                if _EXPORTER_TS.match(st2):
                    ni = len(ls) - len(ls.lstrip(" "))
                    if ni <= indent:
                        break
                i += 1
            continue
        i += 1
        body_lines: list[str] = []
        while i < n:
            ls = lines[i]
            st2 = ls.strip()
            if _EXPORTER_TS.match(st2):
                ni = len(ls) - len(ls.lstrip(" "))
                if ni <= indent:
                    break
            body_lines.append(ls)
            i += 1
        body = "\n".join(body_lines).strip()
        if body:
            bodies.append(body)
    return bodies


def _iter_imessage_exporter_me(
    export_dir: Path, sender_label: str = "Me"
) -> tuple[list[str], int, int]:
    """All ``Me`` bodies from every ``.txt`` in *export_dir* (non-recursive)."""
    out: list[str] = []
    n_files = 0
    for path in sorted(export_dir.iterdir()):
        if not path.is_file() or path.suffix.lower() != ".txt":
            continue
        n_files += 1
        try:
            raw = path.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            print(f"Skip {path.name}: {e}", file=sys.stderr)
            continue
        out.extend(_extract_me_bodies_from_exporter_text(raw, sender_label=sender_label))
    return out, len(out), n_files


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
        help="Skip chat.db iMessage (use with MBOX and/or --imessage-export-dir)",
    )
    p.add_argument(
        "--imessage-export-dir",
        type=Path,
        default=None,
        help="Directory of imessage-exporter -f txt conversation .txt files (extracts sender 'Me' bodies)",
    )
    p.add_argument(
        "--imessage-sender-label",
        type=str,
        default="Me",
        help="Sender line to treat as you (default: Me; use with imessage-exporter --use-caller-id if different)",
    )
    args = p.parse_args()

    since_unix = _parse_since(args.since) if args.since else None

    chunks: list[str] = []
    im_used = im_skip = 0
    ex_used = ex_files = 0
    mbox_messages = 0

    if args.imessage_export_dir is not None:
        d = args.imessage_export_dir.expanduser().resolve()
        if not d.is_dir():
            print(f"Not a directory: {d}", file=sys.stderr)
            raise SystemExit(1)
        ex_lines, ex_used, ex_files = _iter_imessage_exporter_me(
            d, sender_label=args.imessage_sender_label
        )
        if ex_lines:
            chunks.append("=== iMessage (Me only, imessage-exporter txt) ===\n")
            chunks.extend(ex_lines)
            chunks.append("")

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
            mbox_messages += len(parts)
            chunks.append(f"=== Gmail MBOX: {mbox.name} ===\n")
            chunks.extend(parts)
            chunks.append("")

    body = "\n".join(chunks).strip()
    if not body:
        print(
            "Nothing to write — check --imessage-export-dir, chat.db access, date filter, or MBOX paths.",
            file=sys.stderr,
        )
        raise SystemExit(2)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(body + "\n", encoding="utf-8")

    print(f"Wrote {args.out} ({len(body)} characters)")
    if args.imessage_export_dir is not None:
        print(
            f"iMessage exporter: {ex_used} Me messages from {ex_files} .txt files "
            f"({args.imessage_export_dir})."
        )
    if args.mbox:
        print(f"Gmail MBOX: {mbox_messages} sent bodies from {len(args.mbox)} file(s).")
    if not args.skip_imessage:
        print(
            f"iMessage chat.db: {im_used} messages included, {im_skip} outbound rows skipped "
            "(empty text / attributedBody-only — normal on newer macOS)."
        )


if __name__ == "__main__":
    main()
