"""Kitty Builder CLI — Layer 1A (coordination only).

Safe commands:
  brief <task>             print the repo brief for a task
  contract validate <path>  check a builder contract file

Commands intentionally disabled in Layer 1A:
  run, loop, repl, delegate — each prints a clear "not enabled" message.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def _cmd_not_enabled(args: argparse.Namespace) -> int:
    print(
        f"'{args.command}' is not enabled in Kitty Builder Layer 1A.",
        file=sys.stderr,
    )
    print(
        "This layer provides coordination-only commands: brief, contract validate.",
        file=sys.stderr,
    )
    return 1


def _cmd_brief(args: argparse.Namespace) -> int:
    from gateway.brief import build_worker_brief

    packet: dict[str, Any] = {}
    if args.packet:
        packet = json.loads(Path(args.packet).read_text(encoding="utf-8"))
    print(build_worker_brief(" ".join(args.task), packet))
    return 0


def _cmd_contract_validate(args: argparse.Namespace) -> int:
    from gateway.builder_contract import ContractError, load_contract, run_contract

    try:
        spec = load_contract(Path(args.path))
    except ContractError as exc:
        print(f"contract load error: {exc}", file=sys.stderr)
        return 1

    try:
        result = run_contract(spec)
    except ContractError as exc:
        print(f"contract error: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(result, indent=2))
    return 0 if result.get("passed") else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kitty builder",
        description="Kitty Builder control-plane (Layer 1A — coordination only).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="[NOT ENABLED] start a build session")
    run_p.add_argument("goal", nargs="+", help="goal for the builder")
    run_p.set_defaults(func=_cmd_not_enabled)

    loop_p = sub.add_parser("loop", help="[NOT ENABLED] start an interactive session")
    loop_p.add_argument("goal", nargs="+", help="goal for the builder")
    loop_p.set_defaults(func=_cmd_not_enabled)

    repl_p = sub.add_parser("repl", help="[NOT ENABLED] alias for 'loop'")
    repl_p.add_argument("goal", nargs="+", help="goal for the builder")
    repl_p.set_defaults(func=_cmd_not_enabled)

    del_p = sub.add_parser("delegate", help="[NOT ENABLED] hand a task to a worker CLI")
    del_p.add_argument("cli", help="worker CLI alias (e.g. opencode)")
    del_p.add_argument("task", nargs="+", help="task description")
    del_p.set_defaults(func=_cmd_not_enabled)

    brief_p = sub.add_parser("brief", help="print the repo brief for a task")
    brief_p.add_argument("task", nargs="+", help="task description")
    brief_p.add_argument("--packet", help="optional packet JSON file")
    brief_p.set_defaults(func=_cmd_brief)

    contract_p = sub.add_parser("contract", help="builder contract commands")
    contract_sub = contract_p.add_subparsers(dest="contract_command", required=True)
    validate_p = contract_sub.add_parser("validate", help="validate a contract file")
    validate_p.add_argument("path", help="path to JSON or markdown contract")
    validate_p.set_defaults(func=_cmd_contract_validate)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
