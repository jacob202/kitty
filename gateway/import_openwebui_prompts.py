#!/usr/bin/env python3
"""Import Kitty **prompt + skill + tool** library into Open WebUI.

Reads `kitty_openwebui_library.json` (default) or a legacy list-only JSON (prompts only).

Endpoints:
  POST {WEBUI_URL}/api/v1/prompts/create
  POST {WEBUI_URL}/api/v1/skills/create
  POST {WEBUI_URL}/api/v1/tools/create   (Python module must define class ``Tools``)

Auth: WEBUI_URL, WEBUI_ADMIN_EMAIL, WEBUI_ADMIN_PASSWORD (e.g. kitty_gateway/openwebui.env)

Usage:
  ./venv/bin/python kitty_gateway/import_openwebui_prompts.py
  ./venv/bin/python kitty_gateway/import_openwebui_prompts.py --dry-run
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parent.parent
GW = Path(__file__).resolve().parent
DEFAULT_LIBRARY = GW / "kitty_openwebui_library.json"


def load_env() -> None:
    for name in (ROOT / ".env", GW / "openwebui.env"):
        if not name.exists():
            continue
        with open(name, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, _, v = line.partition("=")
                k, v = k.strip(), v.strip().strip('"').strip("'")
                os.environ.setdefault(k, v)


def signin(session: requests.Session, base: str, email: str, password: str) -> None:
    r = session.post(
        f"{base}/api/v1/auths/signin",
        json={"email": email, "password": password},
        timeout=30,
    )
    if r.status_code >= 400:
        print(f"Signin failed: {r.status_code} {r.text[:400]}", file=sys.stderr)
        sys.exit(1)
    token = (r.json() or {}).get("token")
    if not token:
        print("Signin returned no token.", file=sys.stderr)
        sys.exit(1)
    session.headers.update({"Authorization": f"Bearer {token}"})


def parse_library(raw: Any) -> tuple[list, list, list]:
    if isinstance(raw, list):
        return raw, [], []
    if isinstance(raw, dict):
        return (
            raw.get("prompts", []),
            raw.get("skills", []),
            raw.get("tools", []),
        )
    print("Library JSON must be an object {prompts,skills,tools} or a list (prompts only).", file=sys.stderr)
    sys.exit(1)


def main() -> None:
    load_env()
    parser = argparse.ArgumentParser(description="Import Kitty prompts, skills, and tools into Open WebUI")
    parser.add_argument(
        "--library",
        type=Path,
        default=DEFAULT_LIBRARY,
        help="Path to kitty_openwebui_library.json (or legacy prompts-only list JSON)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print actions without POSTing")
    args = parser.parse_args()

    base = os.environ.get("WEBUI_URL", "").rstrip("/")
    email = os.environ.get("WEBUI_ADMIN_EMAIL", "")
    password = os.environ.get("WEBUI_ADMIN_PASSWORD", "")
    if not args.dry_run and (not base or not email or not password):
        print(
            "Set WEBUI_URL, WEBUI_ADMIN_EMAIL, WEBUI_ADMIN_PASSWORD "
            "(e.g. in kitty_gateway/openwebui.env). Omit --dry-run to require auth.",
            file=sys.stderr,
        )
        sys.exit(1)

    data = json.loads(args.library.read_text(encoding="utf-8"))
    prompts, skills, tools = parse_library(data)

    session = requests.Session()
    if not args.dry_run:
        signin(session, base, email, password)

    ok = skip = fail = 0

    for entry in prompts:
        cmd = entry.get("command", "").strip()
        name = entry.get("name", "").strip()
        content = entry.get("content", "").strip()
        tags = entry.get("tags")
        if not cmd or not name or not content:
            print(f"SKIP incomplete prompt: {entry!r}")
            skip += 1
            continue
        body = {
            "command": cmd,
            "name": name,
            "content": content,
            "tags": tags if isinstance(tags, list) else None,
        }
        if args.dry_run:
            print(f"[dry-run] prompt /{cmd} — {name}")
            ok += 1
            continue
        r = session.post(f"{base}/api/v1/prompts/create", json=body, timeout=45)
        if r.status_code == 200:
            print(f"OK  prompt {cmd}")
            ok += 1
        elif r.status_code == 400 and "taken" in (r.text or "").lower():
            print(f"SKIP prompt (command taken) {cmd}")
            skip += 1
        else:
            print(f"FAIL prompt {cmd} {r.status_code} {r.text[:200]}")
            fail += 1

    for entry in skills:
        sid = entry.get("id", "").strip()
        name = entry.get("name", "").strip()
        content = entry.get("content", "").strip()
        if not sid or not name or not content:
            print(f"SKIP incomplete skill: {entry!r}")
            skip += 1
            continue
        meta = dict(entry.get("meta") or {}) if isinstance(entry.get("meta"), dict) else {}
        if not isinstance(meta.get("tags"), list):
            meta["tags"] = []
        body = {
            "id": sid,
            "name": name,
            "description": entry.get("description"),
            "content": content,
            "meta": meta,
            "is_active": entry.get("is_active", True),
        }
        if args.dry_run:
            print(f"[dry-run] skill {sid} — {name}")
            ok += 1
            continue
        r = session.post(f"{base}/api/v1/skills/create", json=body, timeout=45)
        if r.status_code == 200:
            print(f"OK  skill {sid}")
            ok += 1
        elif r.status_code == 400 and "taken" in (r.text or "").lower():
            print(f"SKIP skill (id taken) {sid}")
            skip += 1
        else:
            print(f"FAIL skill {sid} {r.status_code} {r.text[:200]}")
            fail += 1

    for entry in tools:
        tid = entry.get("id", "").strip()
        name = entry.get("name", "").strip()
        rel_path = (entry.get("path") or "").strip()
        desc = entry.get("description", "")
        if not tid or not name or not rel_path:
            print(f"SKIP incomplete tool: {entry!r}")
            skip += 1
            continue
        tool_file = (GW / rel_path).resolve()
        if not str(tool_file).startswith(str(GW.resolve())) or not tool_file.is_file():
            print(f"FAIL tool {tid}: path not under kitty_gateway or missing: {rel_path}", file=sys.stderr)
            fail += 1
            continue
        py_content = tool_file.read_text(encoding="utf-8")
        meta = entry.get("meta") if isinstance(entry.get("meta"), dict) else {}
        manifest = meta.get("manifest") if isinstance(meta.get("manifest"), dict) else {}
        body = {
            "id": tid,
            "name": name,
            "content": py_content,
            "meta": {
                "description": desc or meta.get("description"),
                "manifest": manifest,
            },
        }
        if args.dry_run:
            print(f"[dry-run] tool {tid} — {name} ({rel_path})")
            ok += 1
            continue
        r = session.post(f"{base}/api/v1/tools/create", json=body, timeout=60)
        if r.status_code == 200:
            print(f"OK  tool {tid}")
            ok += 1
        elif r.status_code == 400 and "taken" in (r.text or "").lower():
            print(f"SKIP tool (id taken) {tid}")
            skip += 1
        else:
            print(f"FAIL tool {tid} {r.status_code} {r.text[:200]}")
            fail += 1

    print(f"Done. ok={ok} skip={skip} fail={fail}")
    if fail:
        sys.exit(1)


if __name__ == "__main__":
    main()
