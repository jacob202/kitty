#!/usr/bin/env python3
"""Generate and optionally push Kitty's morning brief.

Usage:
    python scripts/brief.py              # print brief to terminal
    python scripts/brief.py --notify     # print + send Pushover notification
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# Load .env
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

from gateway.brief import generate_brief
from gateway.notify import send_pushover, format_brief_notification


def main():
    parser = argparse.ArgumentParser(description="Generate Kitty's morning brief")
    parser.add_argument("--notify", action="store_true", help="Send via Pushover")
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    args = parser.parse_args()

    print("Generating brief...", flush=True)
    brief = generate_brief()

    if args.json:
        print(json.dumps(brief, indent=2, default=str))
        return

    # Pretty print
    print(f"\n{'='*50}")
    print(f"Kitty Morning Brief — {brief['date']}")
    print(f"{'='*50}")

    if brief.get("intention"):
        print(f"\n{brief['intention']}\n")

    headlines = brief.get("headlines", [])
    if headlines:
        print("News:")
        for h in headlines:
            print(f"  • {h['title']}")
            if h.get("snippet"):
                print(f"    {h['snippet'][:120]}")

    if brief.get("memory_snippet"):
        print(f"\nContext:\n{brief['memory_snippet'][:300]}")

    print(f"\n{'='*50}\n")

    if args.notify:
        title, message = format_brief_notification(brief)
        sent = send_pushover(message, title=title)
        if sent:
            print("Pushover notification sent.")
        else:
            print("Pushover skipped (set PUSHOVER_USER_KEY + PUSHOVER_APP_TOKEN in .env to enable).")


if __name__ == "__main__":
    main()
