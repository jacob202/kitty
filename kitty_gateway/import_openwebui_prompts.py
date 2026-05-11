#!/usr/bin/env python3
"""Import Kitty prompt library into Open WebUI (Workspace → Prompts).

Reads kitty_gateway/kitty_prompt_library.json and POSTs each entry to:
  POST {WEBUI_URL}/api/v1/prompts/create

Requires admin (or prompts_import permission) — same auth as import_openwebui_functions.sh:
  WEBUI_URL, WEBUI_ADMIN_EMAIL, WEBUI_ADMIN_PASSWORD from kitty_gateway/openwebui.env

Usage:
  cd /path/to/kitty && ./venv/bin/python kitty_gateway/import_openwebui_prompts.py
  # or: python3 kitty_gateway/import_openwebui_prompts.py --dry-run
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_LIBRARY = Path(__file__).resolve().parent / "kitty_prompt_library.json"


def load_env():
    for name in (ROOT / ".env", ROOT / "kitty_gateway" / "openwebui.env"):
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


def main() -> None:
    load_env()
    parser = argparse.ArgumentParser(description="Import Kitty prompts into Open WebUI")
    parser.add_argument(
        "--library",
        type=Path,
        default=DEFAULT_LIBRARY,
        help="Path to kitty_prompt_library.json",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print actions without POSTing",
    )
    args = parser.parse_args()

    base = os.environ.get("WEBUI_URL", "").rstrip("/")
    email = os.environ.get("WEBUI_ADMIN_EMAIL", "")
    password = os.environ.get("WEBUI_ADMIN_PASSWORD", "")
    if not base or not email or not password:
        print(
            "Set WEBUI_URL, WEBUI_ADMIN_EMAIL, WEBUI_ADMIN_PASSWORD "
            "(e.g. in kitty_gateway/openwebui.env).",
            file=sys.stderr,
        )
        sys.exit(1)

    data = json.loads(args.library.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        print("Library JSON must be a list of prompt objects.", file=sys.stderr)
        sys.exit(1)

    session = requests.Session()
    if not args.dry_run:
        signin(session, base, email, password)

    ok = skip = fail = 0
    for entry in data:
        cmd = entry.get("command", "").strip()
        name = entry.get("name", "").strip()
        content = entry.get("content", "").strip()
        tags = entry.get("tags")
        if not cmd or not name or not content:
            print(f"SKIP incomplete entry: {entry!r}")
            skip += 1
            continue
        body = {
            "command": cmd,
            "name": name,
            "content": content,
            "tags": tags if isinstance(tags, list) else None,
        }
        if args.dry_run:
            print(f"[dry-run] would create /{cmd} — {name}")
            ok += 1
            continue
        r = session.post(f"{base}/api/v1/prompts/create", json=body, timeout=45)
        if r.status_code == 200:
            print(f"OK  {cmd}")
            ok += 1
        elif r.status_code == 400 and "taken" in (r.text or "").lower():
            print(f"SKIP (command taken) {cmd}")
            skip += 1
        else:
            print(f"FAIL {cmd} {r.status_code} {r.text[:200]}")
            fail += 1

    print(f"Done: ok={ok} skip={skip} fail={fail}")


if __name__ == "__main__":
    main()
