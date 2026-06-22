#!/usr/bin/env python3
"""
Check that the Kitty session continuity state is fresh enough.

Reads docs/AGENT_HANDOFF.md and extracts the most recent date. Exits 0 if the
handoff is within the --max-age-days window, 1 otherwise.

Usage:
  python scripts/check_continuity_state.py --max-age-days 21
"""
import argparse
import re
import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HANDOFF_FILE = ROOT / "docs" / "AGENT_HANDOFF.md"

_DATE_PATTERN = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")


def extract_date(path: Path) -> date:
    """Return the most recent ISO date found in the file."""
    text = path.read_text(encoding="utf-8")
    matches = _DATE_PATTERN.findall(text)
    if not matches:
        raise ValueError(f"No ISO date (YYYY-MM-DD) found in {path}")
    return max(datetime.strptime(d, "%Y-%m-%d").date() for d in matches)


def main() -> int:
    """Parse args, read docs/AGENT_HANDOFF.md, print result, and return exit code."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-age-days", type=int, default=21, metavar="N",
                        help="Maximum allowed age of docs/AGENT_HANDOFF.md in days (default: 21)")
    args = parser.parse_args()

    if not HANDOFF_FILE.exists():
        print(f"FAIL: {HANDOFF_FILE} does not exist")
        return 1

    try:
        handoff_date = extract_date(HANDOFF_FILE)
    except ValueError as exc:
        print(f"FAIL: {exc}")
        return 1

    age_days = (date.today() - handoff_date).days
    if age_days >= args.max_age_days:
        print(
            f"FAIL: docs/AGENT_HANDOFF.md is {age_days} days old "
            f"(limit: {args.max_age_days} days, last updated: {handoff_date})"
        )
        return 1

    print(
        f"OK: docs/AGENT_HANDOFF.md is {age_days} days old "
        f"(limit: {args.max_age_days} days, last updated: {handoff_date})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
