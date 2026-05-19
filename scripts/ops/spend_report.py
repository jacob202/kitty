#!/usr/bin/env python3
"""Print Kitty's token and estimated credit usage report."""
from __future__ import annotations

import argparse

from gateway.token_spend_report import (
    filter_entries,
    format_report,
    load_entries,
    summarize_usage,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--since", help="Only include entries on or after YYYY-MM-DD.")
    parser.add_argument("--provider", help="Only include one provider, e.g. agentrouter.")
    parser.add_argument(
        "--credits",
        type=float,
        help="Known current credit balance to compare against estimated spend.",
    )
    args = parser.parse_args()

    entries = filter_entries(load_entries(), since=args.since, provider=args.provider)
    print(format_report(summarize_usage(entries, credit_balance=args.credits)))


if __name__ == "__main__":
    main()
