#!/usr/bin/env python3
"""Prove whether OpenCode actually loaded and executed session-end."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gateway.session_end_audit import (  # noqa: E402
    SessionEndAuditError,
    audit_session_end,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt-store", type=Path)
    parser.add_argument("--signal-root", type=Path)
    parser.add_argument(
        "--log",
        action="append",
        type=Path,
        default=None,
        help="OpenCode log or log directory to inspect; repeat as needed",
    )
    parser.add_argument(
        "--skill-copy",
        action="append",
        type=Path,
        default=None,
        help="installed session-end skill copy to compare; repeat as needed",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    kwargs = {
        "receipt_store": args.receipt_store,
        "signal_root": args.signal_root,
    }
    if args.log is not None:
        kwargs["log_candidates"] = args.log
    if args.skill_copy is not None:
        kwargs["skill_candidates"] = args.skill_copy
    try:
        result = audit_session_end(**kwargs)
    except SessionEndAuditError as exc:
        print(f"session-end-audit: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result.to_dict(), indent=2, default=str))
    return 0 if result.status == "verified" else 2


if __name__ == "__main__":
    raise SystemExit(main())
