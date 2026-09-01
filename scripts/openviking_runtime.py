#!/usr/bin/env python3
"""Reproducible Kitty-managed OpenViking + embedding Ollama runtime."""
from __future__ import annotations

import argparse
import json
import os
import plistlib
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import httpx

SERVER_LABEL = "com.kitty.openviking-server"
EMBED_LABEL = "com.kitty.openviking-embedding"
DEFAULT_SERVER_URL = "http://127.0.0.1:1933"
DEFAULT_EMBED_URL = "http://127.0.0.1:11435"
DEFAULT_EMBED_MODEL = "nomic-embed-text"


def openviking_home() -> Path:
    return Path(os.environ.get("KITTY_OPENVIKING_HOME", "~/.openviking")).expanduser()


def config_path() -> Path:
    return Path(os.environ.get("KITTY_OPENVIKING_CONFIG", str(openviking_home() / "ov.conf"))).expanduser()


def server_bin(repo_root: Path) -> Path:
    configured = os.environ.get("KITTY_OPENVIKING_SERVER_BIN")
    return Path(configured).expanduser() if configured else repo_root / "venv" / "bin" / "openviking-server"


def ollama_bin() -> Path:
    configured = os.environ.get("OLLAMA_BIN")
    if configured:
        return Path(configured).expanduser()
    found = shutil.which("ollama")
    return Path(found) if found else Path("/opt/homebrew/bin/ollama")


def launch_agents_dir() -> Path:
    return Path(os.environ.get("KITTY_LAUNCH_AGENTS_DIR", "~/Library/LaunchAgents")).expanduser()


def server_url() -> str:
    return os.environ.get("KITTY_OPENVIKING_URL", DEFAULT_SERVER_URL).rstrip("/")


def embed_url() -> str:
    return os.environ.get("KITTY_OPENVIKING_OLLAMA_URL", DEFAULT_EMBED_URL).rstrip("/")


def build_server_plist(repo_root: Path) -> dict[str, Any]:
    home = openviking_home()
    return {
        "Label": SERVER_LABEL,
        "ProgramArguments": [str(server_bin(repo_root)), "--config", str(config_path())],
        "RunAtLoad": True,
        "KeepAlive": True,
        "StandardOutPath": str(home / "server.log"),
        "StandardErrorPath": str(home / "server.err.log"),
    }


def build_embedding_plist(_repo_root: Path) -> dict[str, Any]:
    home = openviking_home()
    return {
        "Label": EMBED_LABEL,
        "ProgramArguments": [str(ollama_bin()), "serve"],
        "EnvironmentVariables": {
            "OLLAMA_HOST": "127.0.0.1:11435",
            "OLLAMA_MODELS": str(Path("~/.ollama/models").expanduser()),
            "OLLAMA_KEEP_ALIVE": "-1",
            "OLLAMA_CONTEXT_LENGTH": "8192",
            "OLLAMA_NUM_PARALLEL": "1",
        },
        "RunAtLoad": True,
        "KeepAlive": True,
        "StandardOutPath": str(home / "embedding-ollama.log"),
        "StandardErrorPath": str(home / "embedding-ollama.err.log"),
    }


def _atomic_plist(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_bytes(plistlib.dumps(payload))
    temp.replace(path)


def install(repo_root: Path) -> list[Path]:
    """Write exact LaunchAgent definitions. Does not restart live services."""
    openviking_home().mkdir(parents=True, exist_ok=True)
    agents = launch_agents_dir()
    outputs = []
    for payload in (build_server_plist(repo_root), build_embedding_plist(repo_root)):
        path = agents / f"{payload['Label']}.plist"
        _atomic_plist(path, payload)
        outputs.append(path)
    return outputs


def _launchctl(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["launchctl", *args], capture_output=True, text=True, timeout=15)


def restart() -> int:
    if sys.platform != "darwin":
        print("restart requires macOS launchd", file=sys.stderr)
        return 2
    domain = f"gui/{os.getuid()}"
    failed = []
    for label in (EMBED_LABEL, SERVER_LABEL):
        result = _launchctl("kickstart", "-k", f"{domain}/{label}")
        if result.returncode != 0:
            failed.append(f"{label}: {result.stderr.strip() or result.stdout.strip()}")
    if failed:
        print("; ".join(failed), file=sys.stderr)
        return 1
    return 0


def uninstall() -> int:
    """Remove only launchd registration/plists; preserve config, models, and workspaces."""
    if sys.platform == "darwin":
        domain = f"gui/{os.getuid()}"
        for label in (SERVER_LABEL, EMBED_LABEL):
            _launchctl("bootout", f"{domain}/{label}")
    for label in (SERVER_LABEL, EMBED_LABEL):
        (launch_agents_dir() / f"{label}.plist").unlink(missing_ok=True)
    return 0


@dataclass(frozen=True)
class ServiceStatus:
    service: str
    ok: bool
    detail: str


def _get_json(url: str) -> tuple[bool, Any]:
    try:
        response = httpx.get(url, timeout=2.0)
        response.raise_for_status()
        return True, response.json()
    except (httpx.HTTPError, ValueError) as exc:
        return False, type(exc).__name__


def probe_server() -> ServiceStatus:
    ok, payload = _get_json(f"{server_url()}/health")
    return ServiceStatus("openviking", ok, "healthy" if ok else f"unavailable:{payload}")


def probe_embedding() -> ServiceStatus:
    ok, payload = _get_json(f"{embed_url()}/api/tags")
    if not ok:
        return ServiceStatus("embedding", False, f"unavailable:{payload}")
    models = payload.get("models") if isinstance(payload, dict) else None
    names = {
        str(row.get("name") or row.get("model") or "").split(":", 1)[0]
        for row in (models or []) if isinstance(row, dict)
    }
    present = DEFAULT_EMBED_MODEL in names
    return ServiceStatus("embedding", present, "model-ready" if present else "server-up-model-missing")


def status_payload() -> dict[str, Any]:
    return {
        "server": asdict(probe_server()),
        "embedding": asdict(probe_embedding()),
        "server_label": SERVER_LABEL,
        "embedding_label": EMBED_LABEL,
        "config": str(config_path()),
        "config_exists": config_path().is_file(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("install", help="write LaunchAgent plists without restarting services")
    sub.add_parser("restart", help="restart already-installed LaunchAgents")
    sub.add_parser("uninstall", help="remove LaunchAgent registration/plists only; preserve data")
    sub.add_parser("status", help="probe server and dedicated embedding runtime")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if args.command == "install":
        for path in install(root):
            print(path)
        return 0
    if args.command == "restart":
        return restart()
    if args.command == "uninstall":
        return uninstall()
    if args.command == "status":
        payload = status_payload()
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0 if payload["server"]["ok"] and payload["embedding"]["ok"] else 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
