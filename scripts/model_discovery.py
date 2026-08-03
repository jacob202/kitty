#!/usr/bin/env python3
"""Discover provider model candidates without changing Kitty's production routes."""

from __future__ import annotations

import argparse
import json
import os
import plistlib
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gateway.model_discovery import (  # noqa: E402
    DISCOVERY_DIR,
    ModelDiscoveryError,
    DiscoveryResult,
    discovery_due,
    discover_openrouter,
    load_snapshot,
)

LABEL = "com.kitty.model-discovery"
LAUNCH_AGENT = Path.home() / f"Library/LaunchAgents/{LABEL}.plist"
LOG_FILE = DISCOVERY_DIR / "model-discovery.log"
START_INTERVAL_SECONDS = 7 * 24 * 60 * 60


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser(
        "check",
        help="record catalogue changes when discovery is due",
    )
    check.add_argument(
        "--force",
        action="store_true",
        help="ignore the weekly cadence",
    )
    check.add_argument(
        "--include-existing",
        action="store_true",
        help="on the first check, queue the entire current catalogue for review",
    )

    sub.add_parser("due", help="report whether a provider check is due")
    sub.add_parser("show", help="show the current candidate snapshot")
    sub.add_parser(
        "install-autostart",
        help="install the weekly local LaunchAgent",
    )
    sub.add_parser(
        "uninstall-autostart",
        help="remove the weekly local LaunchAgent",
    )
    return parser.parse_args()


def launch_agent_plist(*, python: Path | None = None) -> dict[str, Any]:
    """Return a minimal, credential-free weekly discovery service definition."""
    interpreter = python or ROOT / "venv/bin/python"
    if not interpreter.is_file():
        raise ModelDiscoveryError(
            f"Kitty Python is missing at {interpreter}; create the repository venv first"
        )
    return {
        "Label": LABEL,
        "ProgramArguments": [
            str(interpreter),
            str(Path(__file__).resolve()),
            "check",
        ],
        "WorkingDirectory": str(ROOT),
        "RunAtLoad": True,
        "StartInterval": START_INTERVAL_SECONDS,
        "ProcessType": "Background",
        "StandardOutPath": str(LOG_FILE),
        "StandardErrorPath": str(LOG_FILE),
        "EnvironmentVariables": {
            "HOME": str(Path.home()),
            "PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin",
            "PYTHONNOUSERSITE": "1",
            "NO_PROXY": "127.0.0.1,localhost",
            "no_proxy": "127.0.0.1,localhost",
        },
    }


def install_autostart() -> None:
    DISCOVERY_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    DISCOVERY_DIR.chmod(0o700)
    LOG_FILE.touch(mode=0o600, exist_ok=True)
    LOG_FILE.chmod(0o600)
    LAUNCH_AGENT.parent.mkdir(parents=True, exist_ok=True)

    temporary = LAUNCH_AGENT.with_suffix(".plist.tmp")
    try:
        with temporary.open("wb") as handle:
            plistlib.dump(launch_agent_plist(), handle, sort_keys=False)
        temporary.chmod(0o600)
        os.replace(temporary, LAUNCH_AGENT)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise

    domain = f"gui/{os.getuid()}"
    subprocess.run(
        ["launchctl", "bootout", domain, str(LAUNCH_AGENT)],
        check=False,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["launchctl", "enable", f"{domain}/{LABEL}"],
        check=True,
    )
    subprocess.run(
        ["launchctl", "bootstrap", domain, str(LAUNCH_AGENT)],
        check=True,
    )
    print(f"Weekly model discovery installed: {LAUNCH_AGENT}")
    print("Discovery records candidates only; it cannot promote or switch a route.")


def uninstall_autostart() -> None:
    domain = f"gui/{os.getuid()}"
    subprocess.run(
        ["launchctl", "bootout", domain, str(LAUNCH_AGENT)],
        check=False,
        capture_output=True,
        text=True,
    )
    LAUNCH_AGENT.unlink(missing_ok=True)
    print("Weekly model discovery removed; existing snapshots were preserved.")


def notify_result(result: DiscoveryResult) -> None:
    """Surface catalogue changes locally without exposing model/provider secrets."""
    if result.incumbent_removed_roles:
        roles = ", ".join(result.incumbent_removed_roles)
        _notify(
            "Kitty model needs attention",
            f"OpenRouter no longer lists the incumbent for: {roles}.",
        )
        return
    if result.new_models:
        count = len(result.new_models)
        suffix = "candidate" if count == 1 else "candidates"
        _notify(
            "New Kitty model candidates",
            f"{count} new {suffix} recorded for evaluation.",
        )


def _notify(title: str, message: str) -> None:
    executable = shutil.which("osascript")
    if executable is None:
        return
    safe_title = title.replace("\\", "\\\\").replace('"', '\\"')
    safe_message = message.replace("\\", "\\\\").replace('"', '\\"')
    script = (
        f'display notification "{safe_message}" '
        f'with title "{safe_title}"'
    )
    subprocess.run(
        [executable, "-e", script],
        check=False,
        capture_output=True,
        text=True,
    )


def _show(payload: dict[str, Any] | None) -> None:
    if payload is None:
        print(
            json.dumps(
                {
                    "status": "never_checked",
                    "promotion_performed": False,
                },
                indent=2,
            )
        )
        return
    models = payload.get("models", [])
    by_id = {
        item["id"]: item
        for item in models
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    new_models = [
        by_id[model_id]
        for model_id in payload.get("new_model_ids", [])
        if model_id in by_id
    ]
    print(
        json.dumps(
            {
                "provider": payload.get("provider"),
                "checked_at": payload.get("checked_at"),
                "baseline_created": payload.get("baseline_created", False),
                "total_models": len(models),
                "new_models": new_models,
                "removed_model_ids": payload.get("removed_model_ids", []),
                "incumbent_removed_roles": payload.get(
                    "incumbent_removed_roles",
                    [],
                ),
                "promotion_performed": False,
                "next_action": (
                    "Evaluate a candidate with scripts/operating_policy.py "
                    "model-evaluate before editing config/model_roles.json."
                ),
            },
            indent=2,
        )
    )


def main() -> int:
    args = parse_args()
    try:
        if args.command == "check":
            if not args.force and not discovery_due():
                snapshot = load_snapshot()
                print(
                    json.dumps(
                        {
                            "status": "not_due",
                            "checked_at": (
                                snapshot.get("checked_at")
                                if snapshot
                                else None
                            ),
                            "promotion_performed": False,
                        },
                        indent=2,
                    )
                )
                return 0
            result = discover_openrouter(
                include_existing=args.include_existing,
            )
            notify_result(result)
            print(
                json.dumps(
                    {"status": "checked", **result.to_dict()},
                    indent=2,
                )
            )
            return 0
        if args.command == "due":
            due = discovery_due()
            print(
                json.dumps(
                    {"due": due, "promotion_performed": False},
                    indent=2,
                )
            )
            return 0 if due else 3
        if args.command == "show":
            _show(load_snapshot(allow_missing=True))
            return 0
        if args.command == "install-autostart":
            install_autostart()
            return 0
        uninstall_autostart()
        return 0
    except (ModelDiscoveryError, subprocess.CalledProcessError, OSError) as exc:
        print(f"model-discovery: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
