"""CLI renderer for KittyBuilder MCP operator status, doctor, and proof."""

from __future__ import annotations

import argparse
import asyncio
import json
from typing import Any

from . import operator


def _print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))


def _print_human(payload: dict[str, Any]) -> None:
    print(f"KittyBuilder MCP: {payload.get('state', 'unknown')}")
    if payload.get("endpoint"):
        print(f"  endpoint: {payload['endpoint']}")
    process = payload.get("process") or {}
    if process.get("pid"):
        print(f"  pid: {process['pid']}")
    failure = payload.get("first_failure")
    if failure:
        print(f"  first problem: {failure['boundary']} — {failure['summary']}")
    print(f"  next: {payload.get('next_action') or 'none'}")


def _print_proof_human(payload: dict[str, Any]) -> None:
    print(f"MCP proof: {str(payload.get('verdict', 'incomplete')).upper()}")
    print(f"Mission: {payload.get('mission_id') or 'unknown'}")
    print(f"Evidence: {payload.get('receipt_path') or 'not written'}")
    print(f"Next: {payload.get('next_action') or 'inspect proof evidence'}")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="kitty mcp")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("status", "doctor"):
        item = sub.add_parser(name)
        item.add_argument("--json", action="store_true", dest="as_json")
    doctor = sub.choices["doctor"]
    doctor.add_argument("--publication-required", action="store_true")

    proof = sub.add_parser("proof")
    proof.add_argument("mission_id")
    proof.add_argument("--timeout", type=int, default=3600, dest="timeout_seconds")
    proof.add_argument("--poll", type=float, default=2.0, dest="poll_seconds")
    proof.add_argument("--require-publication", action="store_true", dest="publication_required")
    proof.add_argument("--json", action="store_true", dest="as_json")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    config = operator.load_config()
    if args.command == "status":
        payload = operator.status_report(config)
        if args.as_json:
            _print_json(payload)
        else:
            _print_human(payload)
        return 0 if payload.get("ok") else 1

    if args.command == "doctor":
        payload = asyncio.run(
            operator.doctor_report(
                config,
                publication_required=args.publication_required,
            )
        )
        if args.as_json:
            _print_json(payload)
        else:
            _print_human(payload)
        return 0 if payload.get("ok") else 1

    from . import proof as proof_module

    payload = asyncio.run(
        proof_module.proof_report(
            config,
            mission_id=args.mission_id,
            timeout_seconds=args.timeout_seconds,
            poll_seconds=args.poll_seconds,
            publication_required=args.publication_required,
        )
    )
    if args.as_json:
        _print_json(payload)
    else:
        _print_proof_human(payload)
    return {"pass": 0, "fail": 1, "incomplete": 2}.get(
        str(payload.get("verdict")), 2
    )


if __name__ == "__main__":
    raise SystemExit(main())
