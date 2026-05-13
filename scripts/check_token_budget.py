#!/opt/homebrew/bin/python3.12
"""Print a quick usage report from Kitty's token ledger."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gateway.token_spend_report import format_report, load_entries, summarize_usage


def main() -> int:
    entries = load_entries()
    if not entries:
        print("Kitty spend report")
        print("No token ledger entries found.")
        return 0

    print(format_report(summarize_usage(entries)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
