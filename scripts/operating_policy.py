#!/usr/bin/env python3
"""Validate and exercise Kitty's operating contracts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from gateway.operating_policy import (
    OperatingPolicyError,
    evaluate_builder_campaign,
    evaluate_model_candidate,
    load_builder_policy,
    load_model_policy,
    resolve_character_for_engine,
    validate_character_contract,
)


def _json_arg(raw: str) -> dict:
    path = Path(raw).expanduser()
    if path.is_file():
        value = json.loads(path.read_text(encoding="utf-8"))
    else:
        value = json.loads(raw)
    if not isinstance(value, dict):
        raise argparse.ArgumentTypeError("JSON input must be an object")
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("validate", help="validate the checked-in model and Builder policies")

    model = sub.add_parser("model-evaluate", help="evaluate a model-role candidate")
    model.add_argument("--role", required=True, choices=("fast", "think", "code", "vision"))
    model.add_argument("--incumbent", required=True, type=_json_arg)
    model.add_argument("--candidate", required=True, type=_json_arg)

    builder = sub.add_parser("builder-check", help="check campaign economics")
    builder.add_argument("--metrics", required=True, type=_json_arg)

    character = sub.add_parser("character-validate", help="validate one character contract")
    character.add_argument("--character", required=True, type=_json_arg)
    character.add_argument("--engine-capabilities", type=_json_arg)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.command == "validate":
            model = load_model_policy()
            builder = load_builder_policy()
            print(
                json.dumps(
                    {
                        "model_policy": "valid",
                        "model_roles": sorted(model["roles"]),
                        "builder_policy": "valid",
                        "builder_tripwires": sorted(builder["tripwires"]),
                    },
                    indent=2,
                )
            )
            return 0

        if args.command == "model-evaluate":
            result = evaluate_model_candidate(
                args.role,
                args.incumbent,
                args.candidate,
            )
        elif args.command == "builder-check":
            result = evaluate_builder_campaign(args.metrics)
        else:
            validate_character_contract(args.character)
            if args.engine_capabilities is None:
                print(json.dumps({"status": "valid"}, indent=2))
                return 0
            resolved = resolve_character_for_engine(
                args.character,
                args.engine_capabilities,
            )
            print(json.dumps({"status": "valid", "resolved": resolved}, indent=2))
            return 0

        print(json.dumps(result.to_dict(), indent=2))
        return 0 if result.status in {"promote", "continue"} else 2
    except (OperatingPolicyError, json.JSONDecodeError) as exc:
        print(f"operating-policy: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
