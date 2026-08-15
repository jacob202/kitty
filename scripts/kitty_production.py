#!/usr/bin/env python3
"""Canonical production runtime for Kitty.

This is intentionally narrower than ``./kitty`` development startup. A
production release is an immutable clean checkout; mutable data/config/logs
live under ``KITTY_RUNTIME_ROOT``; Gateway and Next bind loopback only; and one
exact provider is selected so chat never depends on the development LiteLLM
proxy/fallback topology.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import socket
import subprocess
import time
from pathlib import Path
from typing import Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]


class ProductionError(RuntimeError):
    pass


_PROVIDER_KEYS: dict[str, tuple[str, ...]] = {
    "openrouter": ("OPENROUTER_API_KEY",),
    "openai": ("OPENAI_API_KEY",),
    "nvidia": ("NVIDIA_API_KEY",),
    "gemini": ("GEMINI_API_KEY",),
    "agentrouter": ("AGENT_ROUTER_TOKEN", "AGENTROUTER_API_KEY"),
}


def git_head() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


def git_dirty() -> bool:
    result = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=normal"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return bool(result.stdout.strip())


def _required(env: Mapping[str, str], name: str) -> str:
    value = str(env.get(name, "")).strip()
    if not value:
        raise ProductionError(f"{name} is required for Kitty production")
    return value


def _runtime_root(env: Mapping[str, str]) -> Path:
    return Path(_required(env, "KITTY_RUNTIME_ROOT")).expanduser().resolve()


def production_env(source: Mapping[str, str] | None = None) -> dict[str, str]:
    env = dict(os.environ if source is None else source)
    runtime = _runtime_root(env)
    env["KITTY_ENV"] = "production"
    env["PYTHON_DOTENV_DISABLED"] = "1"
    env.setdefault("KITTY_DATA_DIR", str(runtime / "data"))
    env.setdefault("KITTY_LOGS_DIR", str(runtime / "logs"))
    env.setdefault("KITTY_CONFIG_DIR", str(runtime / "config"))
    env.setdefault("KITTY_PERSONALITY_DIR", str(runtime / "personality"))
    env.setdefault("KITTY_BUILDER_DATA_DIR", str(runtime / "data" / "kittybuilder"))
    env.setdefault("GATEWAY_HOST", "127.0.0.1")
    env.setdefault("GATEWAY_PORT", "8000")
    env.setdefault("KITTY_UI_HOST", "127.0.0.1")
    env.setdefault("KITTY_UI_PORT", "4000")
    return env


def _is_within(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def preflight(source: Mapping[str, str] | None = None) -> dict[str, str]:
    env = production_env(source)
    if str(env.get("KITTY_ENV", "")).strip().lower() != "production":
        raise ProductionError("KITTY_ENV must be production")
    _required(env, "GATEWAY_SECRET")
    expected = _required(env, "KITTY_EXPECTED_COMMIT")
    runtime = _runtime_root(env)
    if _is_within(runtime, ROOT.resolve()):
        raise ProductionError("KITTY_RUNTIME_ROOT must live outside the release checkout")

    actual = git_head()
    if actual != expected:
        raise ProductionError(f"release HEAD {actual} does not match expected commit {expected}")
    if git_dirty():
        raise ProductionError("release checkout is dirty; production refuses ambiguous code")

    provider = _required(env, "KITTY_ACTIVE_PROVIDER").lower()
    if provider == "auto":
        raise ProductionError("KITTY_ACTIVE_PROVIDER must name one exact provider in production")
    if provider == "local":
        _required(env, "MLX_BASE_URL")
        _required(env, "MLX_MODEL")
    elif provider in _PROVIDER_KEYS:
        if not any(str(env.get(key, "")).strip() for key in _PROVIDER_KEYS[provider]):
            names = " or ".join(_PROVIDER_KEYS[provider])
            raise ProductionError(f"{provider} requires {names}")
    else:
        raise ProductionError(f"unsupported KITTY_ACTIVE_PROVIDER: {provider}")

    if env["GATEWAY_HOST"] not in {"127.0.0.1", "::1", "localhost"}:
        raise ProductionError("production Gateway must bind loopback; publish through the authenticated edge")
    if env["KITTY_UI_HOST"] not in {"127.0.0.1", "::1", "localhost"}:
        raise ProductionError("production UI must bind loopback; publish through the authenticated edge")
    return env


def _copy_missing_tree(source: Path, target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    for item in source.rglob("*"):
        relative = item.relative_to(source)
        destination = target / relative
        if item.is_dir():
            destination.mkdir(parents=True, exist_ok=True)
        elif not destination.exists():
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, destination)


def seed_runtime(source: Mapping[str, str] | None = None) -> dict[str, str]:
    env = production_env(source)
    runtime = _runtime_root(env)
    config_dir = Path(env["KITTY_CONFIG_DIR"])
    personality_dir = Path(env["KITTY_PERSONALITY_DIR"])
    for directory in (
        Path(env["KITTY_DATA_DIR"]),
        Path(env["KITTY_LOGS_DIR"]),
        Path(env["KITTY_BUILDER_DATA_DIR"]),
        runtime / "run",
        config_dir,
        personality_dir,
    ):
        directory.mkdir(parents=True, exist_ok=True)

    _copy_missing_tree(ROOT / "config", config_dir)
    _copy_missing_tree(ROOT / "personality", personality_dir)

    provider = _required(env, "KITTY_ACTIVE_PROVIDER").lower()
    provider_path = config_dir / "providers.json"
    try:
        payload = json.loads(provider_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProductionError(f"cannot read seeded provider configuration: {exc}") from exc
    if not isinstance(payload, dict):
        raise ProductionError("seeded providers.json must be an object")
    payload["active"] = provider
    provider_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    manifest = {
        "release_commit": str(env.get("KITTY_EXPECTED_COMMIT", "")),
        "active_provider": provider,
        "runtime_root": str(runtime),
    }
    (runtime / "runtime.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def service_commands(source: Mapping[str, str] | None = None) -> tuple[list[str], list[str]]:
    env = production_env(source)
    python = ROOT / "venv" / "bin" / "python"
    next_bin = ROOT / "gateway" / "kitty-chat" / "node_modules" / "next" / "dist" / "bin" / "next"
    gateway = [
        str(python), "-m", "uvicorn", "gateway.app:app", "--host", env["GATEWAY_HOST"],
        "--port", env["GATEWAY_PORT"],
    ]
    ui = [
        "node", str(next_bin), "start", "-H", env["KITTY_UI_HOST"], "-p", env["KITTY_UI_PORT"],
    ]
    return gateway, ui


def _pid_path(env: Mapping[str, str], name: str) -> Path:
    return _runtime_root(env) / "run" / f"{name}.pid"


def _log_path(env: Mapping[str, str], name: str) -> Path:
    return Path(env["KITTY_LOGS_DIR"]) / f"production-{name}.log"


def _read_pid(env: Mapping[str, str], name: str) -> int | None:
    try:
        pid = int(_pid_path(env, name).read_text(encoding="utf-8").strip())
        os.kill(pid, 0)
        return pid
    except (FileNotFoundError, ValueError, OSError):
        return None


def _port_in_use(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.3)
        return sock.connect_ex((host, port)) == 0


def _spawn(env: dict[str, str], name: str, command: list[str], cwd: Path) -> int:
    pid_path = _pid_path(env, name)
    pid_path.parent.mkdir(parents=True, exist_ok=True)
    log_path = _log_path(env, name)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("ab") as log:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    pid_path.write_text(str(process.pid), encoding="utf-8")
    return process.pid


def _http_json(url: str, *, bearer: str | None = None, timeout: float = 2.0) -> tuple[int, dict]:
    headers = {"Authorization": f"Bearer {bearer}"} if bearer else {}
    request = Request(url, headers=headers)
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read()
            return response.status, json.loads(raw or b"{}")
    except HTTPError as exc:
        try:
            body = json.loads(exc.read() or b"{}")
        except json.JSONDecodeError:
            body = {}
        return exc.code, body
    except (URLError, TimeoutError, ValueError):
        return 0, {}


def _wait_until(predicate, *, timeout: float = 30.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.25)
    raise ProductionError("production service did not become ready before timeout")


def start(source: Mapping[str, str] | None = None) -> dict[str, object]:
    env = preflight(source)
    seed_runtime(env)
    build_id = ROOT / "gateway" / "kitty-chat" / ".next" / "BUILD_ID"
    if not build_id.is_file():
        raise ProductionError("production UI build missing; run npm ci && npm run build before start")
    gateway_cmd, ui_cmd = service_commands(env)
    if not Path(gateway_cmd[0]).is_file():
        raise ProductionError(f"production Python missing: {gateway_cmd[0]}")
    if not Path(ui_cmd[1]).is_file():
        raise ProductionError(f"production Next server missing: {ui_cmd[1]}")

    owned_gateway = _read_pid(env, "gateway")
    owned_ui = _read_pid(env, "ui")
    gateway_port = int(env["GATEWAY_PORT"])
    ui_port = int(env["KITTY_UI_PORT"])
    if not owned_gateway and _port_in_use(env["GATEWAY_HOST"], gateway_port):
        raise ProductionError(f"Gateway port {gateway_port} is occupied by a process this runtime does not own")
    if not owned_ui and _port_in_use(env["KITTY_UI_HOST"], ui_port):
        raise ProductionError(f"UI port {ui_port} is occupied by a process this runtime does not own")

    gateway_pid = owned_gateway or _spawn(env, "gateway", gateway_cmd, ROOT)
    _wait_until(lambda: _http_json(f"http://127.0.0.1:{gateway_port}/health")[0] == 200)
    ui_pid = owned_ui or _spawn(env, "ui", ui_cmd, ROOT / "gateway" / "kitty-chat")
    _wait_until(lambda: _http_json(f"http://127.0.0.1:{ui_port}/api/identity")[0] == 200)

    ready_status, ready = _http_json(
        f"http://127.0.0.1:{gateway_port}/ready", bearer=env["GATEWAY_SECRET"], timeout=5.0
    )
    if ready_status != 200 or not ready.get("ready"):
        stop(env)
        raise ProductionError(f"Gateway failed production readiness: HTTP {ready_status} {ready}")
    return {
        "ok": True,
        "release_commit": env["KITTY_EXPECTED_COMMIT"],
        "gateway_pid": gateway_pid,
        "ui_pid": ui_pid,
        "gateway_ready": ready,
    }


def stop(source: Mapping[str, str] | None = None) -> dict[str, bool]:
    env = production_env(source)
    result: dict[str, bool] = {}
    for name in ("ui", "gateway"):
        pid = _read_pid(env, name)
        stopped = False
        if pid:
            try:
                os.killpg(pid, signal.SIGTERM)
                stopped = True
            except OSError:
                try:
                    os.kill(pid, signal.SIGTERM)
                    stopped = True
                except OSError:
                    pass
        _pid_path(env, name).unlink(missing_ok=True)
        result[name] = stopped
    return result


def status(source: Mapping[str, str] | None = None) -> dict[str, object]:
    env = production_env(source)
    gateway_port = int(env["GATEWAY_PORT"])
    ui_port = int(env["KITTY_UI_PORT"])
    health_status, health = _http_json(f"http://127.0.0.1:{gateway_port}/health")
    ready_status, ready = _http_json(
        f"http://127.0.0.1:{gateway_port}/ready", bearer=str(env.get("GATEWAY_SECRET", "")) or None
    )
    identity_status, identity = _http_json(f"http://127.0.0.1:{ui_port}/api/identity")
    return {
        "release_commit": str(env.get("KITTY_EXPECTED_COMMIT", "")),
        "gateway_pid": _read_pid(env, "gateway"),
        "ui_pid": _read_pid(env, "ui"),
        "health": {"status": health_status, "body": health},
        "readiness": {"status": ready_status, "body": ready},
        "ui_identity": {"status": identity_status, "body": identity},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("preflight", "seed", "start", "stop", "status"))
    args = parser.parse_args(argv)
    try:
        if args.command == "preflight":
            payload: object = {"ok": True, "environment": preflight()}
        elif args.command == "seed":
            payload = seed_runtime(preflight())
        elif args.command == "start":
            payload = start()
        elif args.command == "stop":
            payload = stop()
        else:
            payload = status()
        # Never print the environment mapping from preflight because it contains
        # secrets. Keep the CLI receipt deliberately bounded.
        if args.command == "preflight":
            payload = {"ok": True, "release_commit": git_head(), "runtime_root": str(_runtime_root(os.environ))}
        print(json.dumps(payload, indent=2, default=str))
        return 0
    except ProductionError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
