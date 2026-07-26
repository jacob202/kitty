"""CLI for the compute governor: dry-run a dispatch, list receipts, read the ledger."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from gateway import compute_governor as cg
from gateway.paths import COMPUTE_GOVERNOR_DB, ROOT

DEFAULT_CONFIG_PATH = ROOT / "config" / "compute_governor.json"


def _load_dispatch(source: str) -> cg.Dispatch:
    raw = sys.stdin.read() if source == "-" else Path(source).read_text(encoding="utf-8")
    return cg.dispatch_from_mapping(json.loads(raw))


def _cmd_explain(args: argparse.Namespace) -> int:
    dispatch = _load_dispatch(args.dispatch)
    config = cg.load_reserve_config(args.config)
    reserve = cg.reserve_from_ledger(args.db, config)
    decision = cg.decide(args.db, dispatch, reserve=reserve, override_reason=args.override)
    if args.json:
        print(json.dumps(decision.to_dict(), indent=2))
    else:
        print(cg.explain(decision))
    # A rejected or deferred dispatch is a non-zero exit so callers can gate on it.
    return 0 if decision.action in {cg.ACTION_RUN, cg.ACTION_DOWNGRADE} else 1


def _cmd_ledger(args: argparse.Namespace) -> int:
    week_of = date.fromisoformat(args.week_of) if args.week_of else None
    ledger = cg.weekly_ledger(args.db, week_of=week_of)
    if args.json:
        print(json.dumps(ledger, indent=2))
        return 0
    print(f"Week {ledger['week_start']} → {ledger['week_end']}")
    print(f"  basis: {ledger['basis']}")
    print(f"  runs: {ledger['runs']}  retries: {ledger['retries']}")
    print(f"  estimated usage: CAD {ledger['estimated_usage_cad']:.4f} (estimate, not a provider meter)")
    for route, amount in ledger["estimated_usage_cad_by_route"].items():
        print(f"    {route}: CAD {amount:.4f}")
    return 0


def _cmd_receipts(args: argparse.Namespace) -> int:
    ledger = cg.weekly_ledger(args.db, week_of=date.fromisoformat(args.week_of) if args.week_of else None)
    entries = ledger["entries"]
    if args.json:
        print(json.dumps(entries, indent=2))
        return 0
    if not entries:
        print("no receipts recorded for this week")
        return 0
    print(cg.summarize_receipts(entries))
    return 0


def _cmd_init(args: argparse.Namespace) -> int:
    cg.init_db(args.db)
    print(f"initialized {args.db}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="kitty governor", description=__doc__)
    parser.add_argument("--db", type=Path, default=COMPUTE_GOVERNOR_DB, help="receipts database")
    sub = parser.add_subparsers(dest="command", required=True)

    explain = sub.add_parser("explain", help="dry-run a dispatch and print why it would run or not")
    explain.add_argument("dispatch", help="path to a dispatch JSON file, or '-' for stdin")
    explain.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    explain.add_argument("--override", help="human override reason for an already-settled pass")
    explain.add_argument("--json", action="store_true")
    explain.set_defaults(func=_cmd_explain)

    ledger = sub.add_parser("ledger", help="weekly local usage estimate")
    ledger.add_argument("--week-of", help="any ISO date inside the week (default: this week)")
    ledger.add_argument("--json", action="store_true")
    ledger.set_defaults(func=_cmd_ledger)

    receipts = sub.add_parser("receipts", help="list this week's recorded passes")
    receipts.add_argument("--week-of", help="any ISO date inside the week (default: this week)")
    receipts.add_argument("--json", action="store_true")
    receipts.set_defaults(func=_cmd_receipts)

    init = sub.add_parser("init", help="create the receipts database")
    init.set_defaults(func=_cmd_init)

    args = parser.parse_args(argv)
    cg.init_db(args.db)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
