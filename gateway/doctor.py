#!/usr/bin/env python3
"""Kitty preflight / health doctor.

Checks the real stack: gateway, LiteLLM, ChromaDB, mem0, Telegram token,
disk space, venv. Exits non-zero when any required check fails.

Usage:
  python gateway/doctor.py              # human-readable table
  python gateway/doctor.py --json       # JSON output
  python gateway/doctor.py --strict     # fail on WARN too
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import shutil
import ssl
import urllib.request
from dataclasses import dataclass


ROOT = pathlib.Path(__file__).resolve().parent.parent


@dataclass
class Check:
    level: str  # PASS | WARN | FAIL
    name: str
    detail: str


def _load_env() -> dict[str, str]:
    env = dict(os.environ)
    dotenv = ROOT / ".env"
    if dotenv.exists():
        for line in dotenv.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            env.setdefault(key.strip(), val.strip().strip('"').strip("'"))
    return env


def _http_ok(url: str, timeout: float = 3.0, headers: dict | None = None) -> bool:
    req = urllib.request.Request(url, headers=headers or {})
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
            return 200 <= r.getcode() < 400
    except Exception:
        return False


def _check_env(env: dict) -> list[Check]:
    out: list[Check] = []

    dotenv = ROOT / ".env"
    if dotenv.exists():
        out.append(Check("PASS", "env:.env", str(dotenv)))
    else:
        out.append(Check("FAIL", "env:.env",
                         f"missing — copy .env.example to {dotenv}"))
        return out  # rest depend on .env

    llm_keys = ["OPENROUTER_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY"]
    set_keys = [k for k in llm_keys if env.get(k, "").strip()]
    if set_keys:
        out.append(Check("PASS", "env:llm_key", f"{set_keys[0]} set"))
    else:
        out.append(Check("FAIL", "env:llm_key",
                         f"none of {llm_keys} set — models will fail"))

    if env.get("KITTY_GATEWAY_SECRET", "").strip() or env.get("GATEWAY_SECRET", "").strip():
        out.append(Check("PASS", "env:gateway_secret", "set"))
    else:
        out.append(Check("WARN", "env:gateway_secret",
                         "not set — auth fails closed for protected routes outside tests"))

    if env.get("TELEGRAM_BOT_TOKEN", "").strip():
        out.append(Check("PASS", "env:telegram_token", "set"))
    else:
        out.append(Check("WARN", "env:telegram_token",
                         "not set — Telegram bot disabled"))

    return out


def _check_services(env: dict) -> list[Check]:
    out: list[Check] = []

    gw_port = env.get("GATEWAY_PORT", "8000")
    gw_url = f"http://127.0.0.1:{gw_port}/health"
    if _http_ok(gw_url):
        out.append(Check("PASS", "service:gateway", gw_url))
    else:
        out.append(Check("FAIL", "service:gateway",
                         f"unreachable: {gw_url} — run: kitty up"))

    ll_port = env.get("LITELLM_PORT", "8001")
    ll_key = env.get("LITELLM_MASTER_KEY", "kitty-local-key-change-me")
    ll_url = f"http://127.0.0.1:{ll_port}/health/readiness"
    if _http_ok(ll_url, timeout=5.0, headers={"Authorization": f"Bearer {ll_key}"}):
        out.append(Check("PASS", "service:litellm", ll_url))
    else:
        out.append(Check("FAIL", "service:litellm",
                         f"unreachable: {ll_url} — run: kitty up"))

    return out


def _check_chromadb() -> list[Check]:
    try:
        import chromadb
        data_dir = ROOT / "data" / "chromadb"
        client = chromadb.PersistentClient(path=str(data_dir))
        colls = client.list_collections()
        return [Check("PASS", "store:chromadb",
                      f"{len(colls)} collection(s) at {data_dir}")]
    except ImportError:
        return [Check("FAIL", "store:chromadb", "chromadb not installed")]
    except Exception as exc:
        return [Check("FAIL", "store:chromadb", f"error: {exc}")]


def _check_mem0(env: dict) -> list[Check]:
    try:
        if env.get("MEM0_API_KEY", "").strip():
            return [Check("PASS", "store:mem0", "API key set")]
        from mem0 import Memory
        _ = Memory()
        return [Check("PASS", "store:mem0", "local mode")]
    except ImportError:
        return [Check("FAIL", "store:mem0", "mem0 not installed")]
    except Exception as exc:
        return [Check("WARN", "store:mem0", f"local init: {exc}")]


def _check_disk() -> list[Check]:
    data_dir = ROOT / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    usage = shutil.disk_usage(data_dir)
    free_gb = usage.free / (1024 ** 3)
    if free_gb >= 2.0:
        return [Check("PASS", "disk:data_dir",
                      f"{free_gb:.1f} GB free at {data_dir}")]
    elif free_gb >= 0.5:
        return [Check("WARN", "disk:data_dir",
                      f"only {free_gb:.1f} GB free")]
    else:
        return [Check("FAIL", "disk:data_dir",
                      f"critically low: {free_gb:.1f} GB free")]


def _check_venv() -> list[Check]:
    venv = ROOT / "venv"
    if (venv / "bin" / "python").exists():
        return [Check("PASS", "runtime:venv", str(venv))]
    return [Check("FAIL", "runtime:venv",
                  f"no venv at {venv} — run: python3.11 -m venv venv && "
                  "venv/bin/pip install -r requirements.txt")]


def _level_order(level: str) -> int:
    return {"PASS": 0, "WARN": 1, "FAIL": 2}.get(level, 2)


def main() -> int:
    parser = argparse.ArgumentParser(description="Kitty health check")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", "--fail-on-warn", action="store_true")
    args = parser.parse_args()

    env = _load_env()
    checks: list[Check] = (
        _check_venv()
        + _check_env(env)
        + _check_services(env)
        + _check_chromadb()
        + _check_mem0(env)
        + _check_disk()
    )

    failures = [c for c in checks if c.level == "FAIL"]
    warns    = [c for c in checks if c.level == "WARN"]
    passes   = [c for c in checks if c.level == "PASS"]

    sorted_checks = sorted(checks, key=lambda c: (_level_order(c.level), c.name))

    if args.json:
        print(json.dumps({
            "summary": {"pass": len(passes), "warn": len(warns), "fail": len(failures)},
            "checks": [{"level": c.level, "name": c.name, "detail": c.detail}
                       for c in sorted_checks],
        }, indent=2))
    else:
        for c in sorted_checks:
            print(f"{c.level:4}  {c.name:<28}  {c.detail}")
        print()
        if not failures and not warns:
            print(f"All {len(passes)} checks passed ✓")
        else:
            print(f"pass={len(passes)}  warn={len(warns)}  fail={len(failures)}")

    if failures:
        return 1
    if args.strict and warns:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
