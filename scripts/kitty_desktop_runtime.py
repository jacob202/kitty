#!/usr/bin/env python3
"""Desktop Phase 1 runtime supervisor.

Starts the Kitty gateway and kitty-chat UI if they are not already running,
tracks pid files for desktop status, and writes a single desktop log.
"""

from __future__ import annotations

import argparse
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent.parent
VENV_PYTHON = ROOT / "venv" / "bin" / "python"
UI_DIR = ROOT / "gateway" / "kitty-chat"
PID_DIR = ROOT / "data" / "desktop" / "run"
LOG_FILE = ROOT / "logs" / "desktop.log"
STOP_GRACE_SECONDS = 5.0
STOP_KILL_SECONDS = 1.0
STOP_POLL_SECONDS = 0.05
HEALTH_WAIT_SECONDS = 5.0
HEALTH_POLL_SECONDS = 0.1

GATEWAY_HOST = os.environ.get("KITTY_DESKTOP_GATEWAY_HOST", "127.0.0.1")
GATEWAY_PORT = int(os.environ.get("KITTY_DESKTOP_GATEWAY_PORT", "8000"))
UI_HOST = os.environ.get("KITTY_DESKTOP_UI_HOST", "127.0.0.1")
UI_PORT = int(os.environ.get("KITTY_DESKTOP_UI_PORT", "4000"))


def pid_file(name: str) -> Path:
    return PID_DIR / f"{name}.pid"


def ensure_dirs() -> None:
    PID_DIR.mkdir(parents=True, exist_ok=True)
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)


def timestamp() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def log(message: str) -> None:
    ensure_dirs()
    with LOG_FILE.open("a", encoding="utf-8") as handle:
        handle.write(f"{timestamp()} {message}\n")


def read_pid(name: str) -> int | None:
    try:
        value = pid_file(name).read_text(encoding="utf-8").strip()
        pid = int(value)
        os.kill(pid, 0)
        return pid
    except (FileNotFoundError, ValueError, OSError):
        return None


def write_pid(name: str, pid: int) -> None:
    ensure_dirs()
    pid_file(name).write_text(str(pid), encoding="utf-8")


def clear_pid(name: str) -> None:
    pid_file(name).unlink(missing_ok=True)


def pid_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def process_cwd(pid: int) -> Path | None:
    try:
        proc = subprocess.run(
            ["lsof", "-a", "-p", str(pid), "-d", "cwd", "-Fn"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None
    for line in proc.stdout.splitlines():
        if line.startswith("n") and len(line) > 1:
            return Path(line[1:]).resolve()
    return None


def pid_owned_by_runtime(name: str, pid: int) -> bool:
    cwd = process_cwd(pid)
    if cwd is None:
        return False
    root = ROOT.resolve()
    return cwd == root or root in cwd.parents


def wait_for_pid_exit(pid: int, timeout: float) -> bool:
    attempts = max(1, int(timeout / STOP_POLL_SECONDS))
    for _ in range(attempts):
        if not pid_running(pid):
            return True
        time.sleep(STOP_POLL_SECONDS)
    return not pid_running(pid)


def port_open(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((host, port)) == 0


def http_ok(url: str) -> bool:
    try:
        with urlopen(url, timeout=1.5) as response:
            return 200 <= response.status < 300
    except (URLError, TimeoutError, ValueError):
        return False


def wait_for_http(url: str) -> bool:
    attempts = max(1, int(HEALTH_WAIT_SECONDS / HEALTH_POLL_SECONDS))
    for _ in range(attempts):
        if http_ok(url):
            return True
        time.sleep(HEALTH_POLL_SECONDS)
    return http_ok(url)


def spawn(
    name: str,
    command: list[str],
    cwd: Path,
    env: dict[str, str] | None = None,
) -> int:
    ensure_dirs()
    with LOG_FILE.open("a", encoding="utf-8") as log_handle:
        process = subprocess.Popen(
            command,
            cwd=str(cwd),
            env=env,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    write_pid(name, process.pid)
    log(f"spawned {name} pid={process.pid} command={' '.join(command)}")
    return process.pid


def ensure_gateway() -> int | None:
    pid = read_pid("gateway")
    if pid and http_ok(f"http://{GATEWAY_HOST}:{GATEWAY_PORT}/health"):
        return pid
    if port_open(GATEWAY_HOST, GATEWAY_PORT) and http_ok(
        f"http://{GATEWAY_HOST}:{GATEWAY_PORT}/health"
    ):
        log("gateway already healthy on port; leaving external process alone")
        return None
    command = [
        str(VENV_PYTHON),
        "-m",
        "uvicorn",
        "gateway.app:app",
        "--host",
        GATEWAY_HOST,
        "--port",
        str(GATEWAY_PORT),
    ]
    return spawn("gateway", command, ROOT)


def ensure_ui() -> int | None:
    pid = read_pid("ui")
    if pid and http_ok(f"http://{UI_HOST}:{UI_PORT}"):
        return pid
    if port_open(UI_HOST, UI_PORT) and http_ok(f"http://{UI_HOST}:{UI_PORT}"):
        log("ui already healthy on port; leaving external process alone")
        return None
    env = os.environ.copy()
    env.setdefault("HOST", UI_HOST)
    env.setdefault("PORT", str(UI_PORT))
    env.setdefault("KITTY_GATEWAY_URL", f"http://{GATEWAY_HOST}:{GATEWAY_PORT}")
    command = ["npm", "run", "dev", "--", "-H", UI_HOST, "-p", str(UI_PORT)]
    return spawn("ui", command, UI_DIR, env=env)


def ensure_all() -> dict[str, object]:
    gateway_url = f"http://{GATEWAY_HOST}:{GATEWAY_PORT}/health"
    ui_url = f"http://{UI_HOST}:{UI_PORT}"

    gateway_pid = ensure_gateway()
    gateway_healthy = wait_for_http(gateway_url)
    # A healthy listener that was already shutting down can disappear after the
    # first point-in-time probe. Only retry discovery when we did not start or
    # claim a PID ourselves; never double-spawn an owned process that is merely
    # slow to become healthy.
    if not gateway_healthy and gateway_pid is None:
        gateway_pid = ensure_gateway()
        gateway_healthy = wait_for_http(gateway_url)

    ui_pid = ensure_ui()
    ui_healthy = wait_for_http(ui_url)
    if not ui_healthy and ui_pid is None:
        ui_pid = ensure_ui()
        ui_healthy = wait_for_http(ui_url)

    return {
        "ok": gateway_healthy and ui_healthy,
        "gateway_pid": gateway_pid or read_pid("gateway"),
        "ui_pid": ui_pid or read_pid("ui"),
        "gateway_healthy": gateway_healthy,
        "ui_healthy": ui_healthy,
        "gateway_url": f"http://{GATEWAY_HOST}:{GATEWAY_PORT}",
        "ui_url": ui_url,
        "log_path": str(LOG_FILE),
    }


def stop_name(name: str) -> bool:
    pid = read_pid(name)
    if not pid:
        clear_pid(name)
        return False
    if not pid_owned_by_runtime(name, pid):
        clear_pid(name)
        log(f"refused to stop unowned {name} pid={pid}; cleared stale pid file")
        return False
    try:
        os.killpg(pid, signal.SIGTERM)
    except OSError:
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass
    if not wait_for_pid_exit(pid, STOP_GRACE_SECONDS):
        try:
            os.killpg(pid, signal.SIGKILL)
        except OSError:
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass
        if not wait_for_pid_exit(pid, STOP_KILL_SECONDS):
            log(f"failed to stop {name} pid={pid}; pid file retained")
            return False
    clear_pid(name)
    log(f"stopped {name} pid={pid}")
    return True


def stop_all() -> dict[str, bool]:
    return {"gateway": stop_name("gateway"), "ui": stop_name("ui")}


def status() -> dict[str, object]:
    return {
        "gateway_pid": read_pid("gateway"),
        "ui_pid": read_pid("ui"),
        "gateway_healthy": http_ok(f"http://{GATEWAY_HOST}:{GATEWAY_PORT}/health"),
        "ui_healthy": http_ok(f"http://{UI_HOST}:{UI_PORT}"),
        "gateway_url": f"http://{GATEWAY_HOST}:{GATEWAY_PORT}",
        "ui_url": f"http://{UI_HOST}:{UI_PORT}",
        "log_path": str(LOG_FILE),
    }


def emit_json(payload: dict[str, object]) -> int:
    import json

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Kitty desktop runtime supervisor")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("ensure")
    sub.add_parser("status")
    sub.add_parser("stop")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "ensure":
        return emit_json(ensure_all())
    if args.command == "status":
        return emit_json(status())
    if args.command == "stop":
        return emit_json(stop_all())
    parser.print_help(sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
