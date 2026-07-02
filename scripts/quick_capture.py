#!/usr/bin/env python3
"""Append a mobile-compatible quick capture to Kitty's local inbox."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gateway.desktop_store import append_text_capture
from gateway.paths import INBOX_FILE


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Save a quick thought to data/inbox.jsonl without starting chat."
    )
    parser.add_argument("text", nargs="*", help="Capture text. Reads stdin when omitted.")
    parser.add_argument(
        "--source",
        default="desktop_quick_capture",
        help="Capture source stored in the inbox entry.",
    )
    parser.add_argument("--project", default=None, help="Optional project label.")
    parser.add_argument(
        "--tag",
        action="append",
        default=[],
        help="Optional tag. Repeat for multiple tags.",
    )
    parser.add_argument(
        "--inbox-file",
        type=Path,
        default=INBOX_FILE,
        help="Override inbox path, primarily for tests.",
    )
    return parser


def main(argv: list[str] | None = None, stdin_text: str | None = None) -> int:
    args = _parser().parse_args(argv)
    text = " ".join(args.text).strip()
    if not text and stdin_text is None and not sys.stdin.isatty():
        stdin_text = sys.stdin.read()
    if not text and stdin_text is not None:
        text = stdin_text.strip()
    if not text:
        print("Nothing captured: provide text or pipe text into quick_capture.py.", file=sys.stderr)
        return 2

    try:
        entry = append_text_capture(
            text=text,
            source=args.source,
            project=args.project,
            tags=args.tag,
            inbox_file=args.inbox_file,
        )
    except ValueError as exc:
        print(f"Nothing captured: {exc}", file=sys.stderr)
        return 2

    print(f"Captured {entry['id']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
