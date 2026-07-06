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
import sys
import urllib.request
from dataclasses import dataclass

ROOT = pathlib.Path(__file__).resolve().parent.parent

# Run as a script (`python gateway/doctor.py`, which is how `kitty doctor`
# invokes it), sys.path[0] is this file's own directory, not the repo root —
# so `from gateway...` imports (connector:mail, push:channel) fail with
# "No module named 'gateway'" regardless of cwd. Put the repo root on the
# path so lazy `gateway.*` imports resolve the same as under pytest.
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


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
        out.append(Check("FAIL", "env:.env", f"missing — copy .env.example to {dotenv}"))
        return out  # rest depend on .env

    llm_keys = ["OPENROUTER_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY"]
    set_keys = [k for k in llm_keys if env.get(k, "").strip()]
    if set_keys:
        out.append(Check("PASS", "env:llm_key", f"{set_keys[0]} set"))
    else:
        out.append(Check("FAIL", "env:llm_key", f"none of {llm_keys} set — models will fail"))

    if env.get("KITTY_GATEWAY_SECRET", "").strip() or env.get("GATEWAY_SECRET", "").strip():
        out.append(Check("PASS", "env:gateway_secret", "set"))
    else:
        out.append(
            Check(
                "WARN",
                "env:gateway_secret",
                "not set — auth fails closed for protected routes outside tests",
            )
        )

    if env.get("TELEGRAM_BOT_TOKEN", "").strip():
        out.append(Check("PASS", "env:telegram_token", "set"))
    else:
        out.append(Check("WARN", "env:telegram_token", "not set — Telegram bot disabled"))

    out.extend(_check_env_parse(dotenv))

    return out


def _check_env_parse(dotenv: pathlib.Path) -> list[Check]:
    """Flag .env lines that python-dotenv can't parse.

    Every python-dotenv consumer prints "could not parse statement starting
    at line N" per bad line per process — a stray quote on line 1 spammed
    nine warnings per `kitty` command live on 2026-07-05. This names the
    exact lines so the fix is a 10-second edit instead of a mystery.
    """
    bad_lines: list[int] = []
    for lineno, raw in enumerate(dotenv.read_text().splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):].lstrip()
        key, sep, _ = line.partition("=")
        if not sep or not key.strip().replace("_", "").isalnum() or key.strip()[0].isdigit():
            bad_lines.append(lineno)

    if not bad_lines:
        return [Check("PASS", "env:parse", "every line parses")]
    shown = ", ".join(str(n) for n in bad_lines[:5])
    more = f" (+{len(bad_lines) - 5} more)" if len(bad_lines) > 5 else ""
    return [
        Check(
            "WARN",
            "env:parse",
            f"unparseable line(s) at {shown}{more} — fix or delete them "
            "(a stray quote or missing '=' breaks python-dotenv loading)",
        )
    ]


def _check_services(env: dict) -> list[Check]:
    out: list[Check] = []

    gw_port = env.get("GATEWAY_PORT", "8000")
    gw_url = f"http://127.0.0.1:{gw_port}/health"
    if _http_ok(gw_url):
        out.append(Check("PASS", "service:gateway", gw_url))
    else:
        out.append(Check("FAIL", "service:gateway", f"unreachable: {gw_url} — run: kitty up"))

    ll_port = env.get("LITELLM_PORT", "8001")
    ll_key = env.get("LITELLM_MASTER_KEY", "kitty-local-key-change-me")
    ll_url = f"http://127.0.0.1:{ll_port}/health/readiness"
    if _http_ok(ll_url, timeout=5.0, headers={"Authorization": f"Bearer {ll_key}"}):
        out.append(Check("PASS", "service:litellm", ll_url))
    else:
        out.append(Check("FAIL", "service:litellm", f"unreachable: {ll_url} — run: kitty up"))

    return out


def _check_chromadb() -> list[Check]:
    try:
        import chromadb

        data_dir = ROOT / "data" / "chromadb"
        client = chromadb.PersistentClient(path=str(data_dir))
        colls = client.list_collections()
        return [Check("PASS", "store:chromadb", f"{len(colls)} collection(s) at {data_dir}")]
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
    free_gb = usage.free / (1024**3)
    if free_gb >= 2.0:
        return [Check("PASS", "disk:data_dir", f"{free_gb:.1f} GB free at {data_dir}")]
    elif free_gb >= 0.5:
        return [Check("WARN", "disk:data_dir", f"only {free_gb:.1f} GB free")]
    else:
        return [Check("FAIL", "disk:data_dir", f"critically low: {free_gb:.1f} GB free")]


def _check_mail_connector(env: dict) -> list[Check]:
    """Three states: PASS (token present and loadable), WARN (pre-OAuth),
    FAIL (configured but broken — token unreadable or refresh failed)."""
    try:
        # Imported lazily so doctor runs on a host without google-auth.
        from gateway.connectors import mail as mail_connector
    except ImportError as exc:
        return [Check("FAIL", "connector:mail", f"import error: {exc}")]

    token_env = env.get("GMAIL_TOKEN_FILE", "").strip()
    token_path = ROOT / token_env if token_env else ROOT / "data" / "gmail_token.json"
    if not token_path.exists():
        return [
            Check(
                "WARN",
                "connector:mail",
                "token file not present — run: python -m gateway.connectors.mail --auth",
            )
        ]

    # Token file exists — try to load it. A malformed file is FAIL.
    try:
        creds = mail_connector._load_credentials()
    except mail_connector.MailAuthError as exc:
        return [Check("FAIL", "connector:mail", f"token unreadable: {exc}")]
    except Exception as exc:  # noqa: BLE001
        return [Check("FAIL", "connector:mail", f"unexpected: {exc}")]

    if getattr(creds, "expired", False) and not getattr(creds, "refresh_token", None):
        return [Check("FAIL", "connector:mail", "expired and no refresh token — re-authorize")]

    detail = f"token at {token_path}"
    if getattr(creds, "expired", False):
        detail += " (expired, refresh pending)"
    return [Check("PASS", "connector:mail", detail)]


def _check_push_channel(env: dict) -> list[Check]:
    """PASS when a channel is configured and the last logged attempt (if any)
    succeeded; WARN when nothing is configured; FAIL when the last attempt
    failed."""
    from gateway import push

    channels = [c.strip() for c in env.get("PUSH_CHANNELS", "imessage,pushover").split(",") if c.strip()]
    imessage_ready = bool(env.get("PUSH_IMESSAGE_RECIPIENT", "").strip())
    pushover_ready = bool(env.get("PUSHOVER_USER_KEY", "").strip()) and bool(
        env.get("PUSHOVER_API_TOKEN", "").strip()
    )
    configured = ("imessage" in channels and imessage_ready) or ("pushover" in channels and pushover_ready)

    if not configured:
        return [
            Check(
                "WARN",
                "push:channel",
                "no channel configured — set PUSH_IMESSAGE_RECIPIENT or "
                "PUSHOVER_USER_KEY/PUSHOVER_API_TOKEN",
            )
        ]

    entries = push._recent_log_entries()
    if not entries:
        return [Check("PASS", "push:channel", f"configured ({', '.join(channels)}) — no attempts logged yet")]

    last = entries[-1]
    if last.get("ok"):
        return [Check("PASS", "push:channel", f"last attempt via {last.get('channel')} succeeded")]
    return [
        Check(
            "FAIL",
            "push:channel",
            f"last attempt via {last.get('channel')} failed — check logs/push_log.jsonl",
        )
    ]


def _check_deadlines() -> list[Check]:
    """PASS when deadlines are being watched and last push succeeded; WARN when none watched; FAIL on last push failure."""
    from gateway import deadline_store, push

    open_deadlines = deadline_store.list_open(status="open")
    if not open_deadlines:
        return [Check("WARN", "deadlines:watch", "no open deadlines being watched")]

    entries = push._recent_log_entries()
    deadline_entries = [e for e in entries if e.get("dedupe_key", "").startswith("deadline-")]
    if not deadline_entries:
        return [Check("PASS", "deadlines:watch", f"{len(open_deadlines)} open deadline(s) — no pushes yet")]

    last = deadline_entries[-1]
    if last.get("ok"):
        return [Check("PASS", "deadlines:watch", f"{len(open_deadlines)} open deadline(s); last push via {last.get('channel')} succeeded")]
    return [
        Check(
            "FAIL",
            "deadlines:watch",
            f"last deadline push via {last.get('channel')} failed — check logs/push_log.jsonl",
        )
    ]


def _check_venv() -> list[Check]:
    venv = ROOT / "venv"
    if (venv / "bin" / "python").exists():
        return [Check("PASS", "runtime:venv", str(venv))]
    return [
        Check(
            "FAIL",
            "runtime:venv",
            f"no venv at {venv} — run: python3.11 -m venv venv && "
            "venv/bin/pip install -r requirements.txt",
        )
    ]


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
        + _check_mail_connector(env)
        + _check_push_channel(env)
        + _check_deadlines()
    )

    failures = [c for c in checks if c.level == "FAIL"]
    warns = [c for c in checks if c.level == "WARN"]
    passes = [c for c in checks if c.level == "PASS"]

    sorted_checks = sorted(checks, key=lambda c: (_level_order(c.level), c.name))

    if args.json:
        print(
            json.dumps(
                {
                    "summary": {"pass": len(passes), "warn": len(warns), "fail": len(failures)},
                    "checks": [
                        {"level": c.level, "name": c.name, "detail": c.detail}
                        for c in sorted_checks
                    ],
                },
                indent=2,
            )
        )
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
