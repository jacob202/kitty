#!/usr/bin/env python3
"""Print Kitty's weekly pattern mirror."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
except ImportError:
    pass

from gateway.honcho import get_weekly_mirror

mirror = get_weekly_mirror(use_cache=False)
date_str = str(mirror.get("timestamp", ""))[:10]
trace_count = mirror.get("metadata", {}).get("trace_count", "?")

print(f"\n=== Kitty's Weekly Mirror — {date_str} ===\n")
print(mirror["observation"])
print(f"\n(Based on {trace_count} conversations this week)")
