from __future__ import annotations

import argparse
import subprocess
import sys

from .common import Failure, install_openwebui
from .service import (
    direct_stream_smoke,
    doctor,
    open_browser,
    print_status,
    show_logs,
    start_webui,
    stop_webui,
)
from .system import bootstrap, install_launch_agent, uninstall_launch_agent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Install, run, and verify Open WebUI backed by Kitty Gateway"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    bootstrap_parser = subparsers.add_parser("bootstrap")
    bootstrap_parser.add_argument("--accept-charges", action="store_true")
    bootstrap_parser.add_argument("--no-autostart", action="store_true")

    commands = (
        "install",
        "up",
        "service",
        "down",
        "status",
        "doctor",
        "logs",
        "open",
        "install-autostart",
        "uninstall-autostart",
    )
    for name in commands:
        subparsers.add_parser(name)

    smoke_parser = subparsers.add_parser("smoke")
    smoke_parser.add_argument("--accept-charges", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.command == "bootstrap":
            bootstrap(
                accept_charges=args.accept_charges,
                no_autostart=args.no_autostart,
            )
        elif args.command == "install":
            install_openwebui()
        elif args.command == "up":
            start_webui()
            open_browser()
        elif args.command == "service":
            start_webui(foreground=True)
        elif args.command == "down":
            stop_webui()
        elif args.command == "status":
            print_status()
        elif args.command == "doctor":
            doctor()
        elif args.command == "logs":
            show_logs()
        elif args.command == "smoke":
            direct_stream_smoke(accept_charges=args.accept_charges)
        elif args.command == "open":
            open_browser()
        elif args.command == "install-autostart":
            install_launch_agent()
        elif args.command == "uninstall-autostart":
            uninstall_launch_agent()
    except Failure as exc:
        print(f"openwebui-local: {exc}", file=sys.stderr)
        return 1
    except subprocess.CalledProcessError as exc:
        command = " ".join(map(str, exc.cmd))
        print(
            f"openwebui-local: command failed ({exc.returncode}): {command}",
            file=sys.stderr,
        )
        return exc.returncode or 1
    return 0
