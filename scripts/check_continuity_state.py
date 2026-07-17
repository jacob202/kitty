#!/usr/bin/env python3
"""Validate Kitty's complete repository continuity contract.

This is the CI-friendly wrapper over the same checks used by
``./kitty context --agent`` and ``./kitty doctor``. It does not repair, fetch,
or mutate state.

Environment overrides (for CI runners whose checkout does not live under
``~/Projects/kitty``):

- ``KITTY_EXPECTED_CANONICAL_CHECKOUT`` — absolute path the runner used for
  the checkout. When set, ``repo:canonical_checkout`` compares against this
  instead of the default ``~/Projects/kitty``.
"""
import argparse
import json
import os
import sys
from dataclasses import asdict
from datetime import timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# Put this checkout first even when an ambient PYTHONPATH names another Kitty
# worktree. Continuity checks must inspect the checkout that owns this script.
sys.path.insert(0, str(ROOT))

from gateway.context_receipt import (  # noqa: E402
    ContextReceiptError,
    run_continuity_checks,
)


def main(argv: list[str] | None = None) -> int:
    """Print every continuity check and fail when any check fails."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--max-age-days",
        type=int,
        default=7,
        metavar="N",
        help="maximum age of active STATE/HANDOFF checkpoints (default: 7)",
    )
    parser.add_argument("--json", action="store_true", help="emit structured JSON")
    parser.add_argument(
        "--expected-canonical",
        type=Path,
        default=None,
        metavar="PATH",
        help="override the expected canonical checkout path "
        "(defaults to $KITTY_EXPECTED_CANONICAL_CHECKOUT if set, then ~/Projects/kitty)",
    )
    args = parser.parse_args(argv)
    if args.max_age_days < 0:
        parser.error("--max-age-days must be zero or greater")
    expected_canonical = args.expected_canonical
    if expected_canonical is None:
        env_override = os.environ.get("KITTY_EXPECTED_CANONICAL_CHECKOUT")
        if env_override:
            expected_canonical = Path(env_override)
    try:
        checks = run_continuity_checks(
            ROOT,
            expected_canonical=expected_canonical,
            max_age=timedelta(days=args.max_age_days),
        )
    except (ContextReceiptError, OSError, RuntimeError, ValueError) as exc:
        print(f"FAIL: continuity checks could not run: {type(exc).__name__}: {exc}")
        return 1
    failures = [check for check in checks if check.level == "FAIL"]
    if args.json:
        payload = {
            "ok": not failures,
            "summary": {
                "pass": sum(check.level == "PASS" for check in checks),
                "warn": sum(check.level == "WARN" for check in checks),
                "fail": len(failures),
            },
            "checks": [asdict(check) for check in checks],
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        for check in checks:
            print(f"{check.level}: {check.name}: {check.detail}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
