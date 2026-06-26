#!/usr/bin/env python3
"""Generate and manage the macOS LaunchAgents for the Kitty Desktop service stack.

Three per-user LaunchAgents own the always-on local services so that Kitty
survives logout/login and reboot without a Terminal:

    com.kitty.desktop.litellm  -> 127.0.0.1:8001
    com.kitty.desktop.gateway  -> 127.0.0.1:8000
    com.kitty.desktop.ui       -> 127.0.0.1:4000

launchd owns the service lifecycle (start at login, keep alive, throttle crash
loops, capture stdout/stderr). This module is deliberately small: it only
renders plists and builds *fixed* launchctl argument vectors against a strict
label allowlist. It never embeds a secret in a plist — the service wrapper
scripts load `.env` at start time. Loopback binding is pinned in the plist
environment so a misconfigured wrapper cannot expose a service to the network.

The launchctl-executing commands are guarded to macOS. Plist rendering and
validation are pure and run anywhere, which is what the test-suite exercises.
"""

from __future__ import annotations

import argparse
import os
import plistlib
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

LABEL_PREFIX = "com.kitty.desktop"

# Loopback PATH that survives launchd's stripped GUI-login environment. The
# canonical start scripts activate their own venvs, but node/npm and the system
# tools still need to be discoverable.
LOGIN_SAFE_PATH = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

# Seconds launchd waits before restarting a service that keeps exiting. Without
# this a service with a bad key would crash-restart in a tight loop.
THROTTLE_INTERVAL = 10


@dataclass(frozen=True)
class Service:
    """A single managed service.

    `program` is resolved to an absolute path under the repo root at render
    time. `env` carries only non-secret config; loopback host pinning lives
    here so it is enforced regardless of wrapper defaults.
    """

    name: str
    program: str  # relative to repo root
    env: dict[str, str]

    @property
    def label(self) -> str:
        return f"{LABEL_PREFIX}.{self.name}"


SERVICES: dict[str, Service] = {
    "litellm": Service(
        name="litellm",
        program="gateway/start_litellm.sh",
        env={"LITELLM_HOST": "127.0.0.1", "LITELLM_PORT": "8001"},
    ),
    "gateway": Service(
        name="gateway",
        program="gateway/start_gateway.sh",
        env={"GATEWAY_HOST": "127.0.0.1", "GATEWAY_PORT": "8000"},
    ),
    "ui": Service(
        name="ui",
        program="scripts/desktop/start_ui.sh",
        env={
            "KITTY_UI_HOST": "127.0.0.1",
            "KITTY_UI_PORT": "4000",
            "KITTY_GATEWAY_URL": "http://127.0.0.1:8000",
        },
    ),
}

# Ordered for dependency-friendly startup/shutdown (litellm first, ui last).
SERVICE_ORDER = ["litellm", "gateway", "ui"]


def repo_root_default() -> Path:
    """Repo root inferred from this file's location (scripts/ -> root)."""
    return Path(__file__).resolve().parents[1]


def launchagents_dir() -> Path:
    return Path.home() / "Library" / "LaunchAgents"


def is_linked_git_worktree(repo_root: Path) -> bool:
    """Linked git worktrees use a .git file that points at another git dir."""
    return (repo_root / ".git").is_file()


def validate_install_root(repo_root: Path, *, allow_worktree_install: bool = False) -> None:
    """Refuse launchd installs from disposable worktrees unless made explicit."""
    root = repo_root.resolve()
    if is_linked_git_worktree(root) and not allow_worktree_install:
        raise RuntimeError(
            "Refusing to install LaunchAgents from a linked git worktree at "
            f"{root}. Run from the canonical repo checkout or pass "
            "--allow-worktree-install if this path is intentionally permanent."
        )


def plist_path(name: str) -> Path:
    return launchagents_dir() / f"{SERVICES[_require(name)].label}.plist"


def log_paths(name: str, repo_root: Path) -> tuple[Path, Path]:
    """(stdout, stderr) log paths for a service, under logs/desktop/."""
    base = repo_root / "logs" / "desktop"
    return base / f"{name}.log", base / f"{name}.err.log"


def _require(name: str) -> str:
    """Validate a service name against the allowlist. Raises on anything else."""
    if name not in SERVICES:
        raise ValueError(
            f"unknown service {name!r}; expected one of {sorted(SERVICES)}"
        )
    return name


def resolve_targets(name: str) -> list[str]:
    """Expand a CLI target ('all' or one service) into ordered service names."""
    if name == "all":
        return list(SERVICE_ORDER)
    return [_require(name)]


def build_plist(name: str, repo_root: Path | None = None) -> dict:
    """Render the plist dict for one service. Pure; safe to call anywhere."""
    svc = SERVICES[_require(name)]
    root = (repo_root or repo_root_default()).resolve()
    out_log, err_log = log_paths(name, root)

    environment = {"PATH": LOGIN_SAFE_PATH, **svc.env}

    return {
        "Label": svc.label,
        "ProgramArguments": ["/bin/bash", str(root / svc.program)],
        "WorkingDirectory": str(root),
        "EnvironmentVariables": environment,
        "RunAtLoad": True,
        # Restart on crash, but not after a clean exit (SuccessfulExit: False).
        "KeepAlive": {"SuccessfulExit": False},
        "ThrottleInterval": THROTTLE_INTERVAL,
        "ProcessType": "Interactive",
        "StandardOutPath": str(out_log),
        "StandardErrorPath": str(err_log),
    }


def render_plist_bytes(name: str, repo_root: Path | None = None) -> bytes:
    """Serialize a service plist to XML bytes (plistlib handles escaping)."""
    return plistlib.dumps(build_plist(name, repo_root))


# --------------------------------------------------------------------------- #
# launchctl lifecycle (macOS only)
# --------------------------------------------------------------------------- #


def _require_macos() -> None:
    if sys.platform != "darwin":
        raise RuntimeError(
            "launchctl operations are macOS-only; "
            "use the generate/validate commands on other platforms"
        )


def _domain_target(label: str) -> str:
    return f"gui/{os.getuid()}/{label}"


def _run(args: list[str]) -> subprocess.CompletedProcess:
    _require_macos()
    return subprocess.run(args, capture_output=True, text=True, check=False)


def install(
    repo_root: Path | None = None, *, allow_worktree_install: bool = False
) -> list[Path]:
    """Write all plists and ensure the log directory exists. Idempotent."""
    root = (repo_root or repo_root_default()).resolve()
    validate_install_root(root, allow_worktree_install=allow_worktree_install)
    launchagents_dir().mkdir(parents=True, exist_ok=True)
    (root / "logs" / "desktop").mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name in SERVICE_ORDER:
        path = plist_path(name)
        path.write_bytes(render_plist_bytes(name, root))
        written.append(path)
    return written


def bootstrap(name: str) -> None:
    for svc_name in resolve_targets(name):
        label = SERVICES[svc_name].label
        path = plist_path(svc_name)
        _run(["launchctl", "bootstrap", f"gui/{os.getuid()}", str(path)])
        _run(["launchctl", "enable", _domain_target(label)])


def bootout(name: str) -> None:
    for svc_name in resolve_targets(name):
        _run(["launchctl", "bootout", _domain_target(SERVICES[svc_name].label)])


def restart(name: str) -> None:
    for svc_name in resolve_targets(name):
        _run(["launchctl", "kickstart", "-k", _domain_target(SERVICES[svc_name].label)])


def status(name: str = "all") -> dict[str, str]:
    """Return launchctl print output per service (diagnostic context only)."""
    result: dict[str, str] = {}
    for svc_name in resolve_targets(name):
        proc = _run(["launchctl", "print", _domain_target(SERVICES[svc_name].label)])
        result[svc_name] = proc.stdout or proc.stderr
    return result


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("generate", help="print plists to stdout (no writes)")
    install_parser = sub.add_parser("install", help="write plists to ~/Library/LaunchAgents")
    install_parser.add_argument(
        "--allow-worktree-install",
        action="store_true",
        help="allow plists to point at a linked git worktree path",
    )

    targets = list(SERVICE_ORDER) + ["all"]
    for cmd, help_text in [
        ("bootstrap", "bootstrap + enable launchd job(s)"),
        ("bootout", "remove launchd job(s)"),
        ("restart", "kickstart -k launchd job(s)"),
        ("status", "print launchd job state"),
    ]:
        p = sub.add_parser(cmd, help=help_text)
        p.add_argument("target", choices=targets, nargs="?", default="all")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    if args.command == "generate":
        for name in SERVICE_ORDER:
            print(f"# === {SERVICES[name].label} ===")
            print(render_plist_bytes(name).decode("utf-8"))
        return 0
    if args.command == "install":
        try:
            for path in install(allow_worktree_install=args.allow_worktree_install):
                print(f"wrote {path}")
            return 0
        except RuntimeError as error:
            print(f"Error: {error}", file=sys.stderr)
            return 1
    if args.command == "bootstrap":
        bootstrap(args.target)
    elif args.command == "bootout":
        bootout(args.target)
    elif args.command == "restart":
        restart(args.target)
    elif args.command == "status":
        for name, text in status(args.target).items():
            print(f"# === {name} ===\n{text}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
