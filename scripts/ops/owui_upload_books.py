#!/usr/bin/env python3
"""Upload a books manifest into categorized Open WebUI knowledge bases.

This is intentionally separate from ``assign_kb_files.py``:
- upload files from disk via ``/api/v1/files/``
- then attach each uploaded file to the category KB via ``/knowledge/{id}/file/add``

Credentials are read from environment first, then from
``kitty_gateway/openwebui.env`` using the non-secret variable names already used
by the local Open WebUI launcher.
"""

from __future__ import annotations

import argparse
import mimetypes
import os
import re
import sqlite3
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ENV_FILE = ROOT / "kitty_gateway/openwebui.env"
DEFAULT_MANIFEST = ROOT / "data/books_ingest_manifest.txt"
DEFAULT_DB = Path.home() / "kitty-services/open-webui-data/webui.db"

sys.path.insert(0, str(ROOT))
from scripts.assign_kb_files import FALLBACK_KB, KB_DEFS, classify  # noqa: E402


def _parse_env_value(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    return value.replace("$HOME", str(Path.home()))


def load_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    pattern = re.compile(r"^(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)=(.*)$")
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = pattern.match(line)
        if match:
            values[match.group(1)] = _parse_env_value(match.group(2))
    return values


def setting(name: str, env_file: dict[str, str], *fallback_names: str, default: str = "") -> str:
    if os.environ.get(name):
        return os.environ[name]
    for fallback in fallback_names:
        if os.environ.get(fallback):
            return os.environ[fallback]
    if name in env_file:
        return env_file[name]
    for fallback in fallback_names:
        if fallback in env_file:
            return env_file[fallback]
    return default


def login(url: str, email: str, password: str) -> str:
    if not email or not password:
        raise SystemExit(
            "Missing Open WebUI credentials. Set OWUI_EMAIL/OWUI_PASSWORD or "
            "WEBUI_ADMIN_EMAIL/WEBUI_ADMIN_PASSWORD."
        )
    response = requests.post(
        f"{url}/api/v1/auths/signin",
        json={"email": email, "password": password},
        timeout=20,
    )
    response.raise_for_status()
    token = response.json().get("token")
    if not token:
        raise SystemExit("Open WebUI login succeeded but no token was returned.")
    return token


def get_existing_kbs(url: str, token: str) -> dict[str, str]:
    response = requests.get(
        f"{url}/api/v1/knowledge/",
        headers={"Authorization": f"Bearer {token}"},
        timeout=20,
    )
    response.raise_for_status()
    data = response.json()
    items = data["items"] if isinstance(data, dict) else data
    return {item["name"]: item["id"] for item in items}


def create_kb(url: str, token: str, name: str, description: str) -> str:
    response = requests.post(
        f"{url}/api/v1/knowledge/create",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": name, "description": description, "data": {}},
        timeout=20,
    )
    response.raise_for_status()
    return response.json()["id"]


def ensure_kbs(url: str, token: str, dry_run: bool) -> dict[str, str]:
    kb_map = get_existing_kbs(url, token)
    for name, description, _ in list(KB_DEFS) + [(*FALLBACK_KB, [])]:
        if name in kb_map:
            continue
        if dry_run:
            print(f"[dry-run] would create KB: {name}")
            continue
        kb_map[name] = create_kb(url, token, name, description)
        print(f"created KB: {name}")
    return kb_map


def existing_uploaded_files(db_path: Path) -> dict[str, str]:
    if not db_path.exists():
        return {}
    conn = sqlite3.connect(str(db_path))
    try:
        rows = conn.execute("SELECT filename, id FROM file ORDER BY created_at ASC").fetchall()
    finally:
        conn.close()
    files: dict[str, str] = {}
    for filename, file_id in rows:
        files[filename] = file_id
    return files


def already_in_kb(db_path: Path, kb_id: str) -> set[str]:
    if not db_path.exists():
        return set()
    conn = sqlite3.connect(str(db_path))
    try:
        rows = conn.execute(
            "SELECT file_id FROM knowledge_file WHERE knowledge_id=?",
            (kb_id,),
        ).fetchall()
    finally:
        conn.close()
    return {row[0] for row in rows}


def upload_file(url: str, token: str, path: Path) -> str:
    mime_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    with path.open("rb") as handle:
        response = requests.post(
            f"{url}/api/v1/files/",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": (path.name, handle, mime_type)},
            timeout=180,
        )
    response.raise_for_status()
    file_id = response.json().get("id")
    if not file_id:
        raise RuntimeError(f"upload returned no file id for {path}")
    return file_id


def add_to_kb(url: str, token: str, kb_id: str, file_id: str) -> str:
    response = requests.post(
        f"{url}/api/v1/knowledge/{kb_id}/file/add",
        headers={"Authorization": f"Bearer {token}"},
        json={"file_id": file_id},
        timeout=180,
    )
    if response.ok:
        try:
            body = response.json()
        except ValueError:
            body = {}
        if "detail" not in body:
            return "added"
    detail = ""
    if "duplicate" in response.text.lower() or "already" in response.text.lower():
        return "already"
    try:
        detail = str(response.json().get("detail", ""))
    except Exception:
        detail = ""
    if "content provided is empty" in response.text.lower() or "content provided is empty" in detail.lower():
        return "empty"
    raise RuntimeError(f"KB add failed ({response.status_code}): {response.text[:200]}")


def read_manifest(path: Path) -> list[Path]:
    files = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        item = raw.strip()
        if item:
            files.append(Path(item).expanduser())
    return files


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_FILE)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--url", default="")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--pause", type=float, default=0.1)
    args = parser.parse_args()

    env_file = load_env_file(args.env_file)
    url = args.url or setting("OWUI_URL", env_file, "WEBUI_URL", default="http://127.0.0.1:3000")
    email = setting("OWUI_EMAIL", env_file, "WEBUI_ADMIN_EMAIL")
    password = setting("OWUI_PASSWORD", env_file, "WEBUI_ADMIN_PASSWORD")

    files = [path for path in read_manifest(args.manifest) if path.exists()]
    if args.limit:
        files = files[: args.limit]
    print(f"manifest: {args.manifest}")
    print(f"files found: {len(files)}")
    if not files:
        return 0

    token = login(url, email, password)
    kb_map = ensure_kbs(url, token, args.dry_run)
    uploaded = existing_uploaded_files(args.db)

    added = reused = skipped = failed = 0
    total = len(files)
    for index, path in enumerate(files, 1):
        kb_name = classify(path.name)
        kb_id = kb_map[kb_name]
        print(f"[{index}/{total}] {path.name} -> {kb_name}", flush=True)

        if args.dry_run:
            skipped += 1
            continue

        try:
            file_id = uploaded.get(path.name)
            if file_id:
                reused += 1
            else:
                file_id = upload_file(url, token, path)
                uploaded[path.name] = file_id

            if file_id in already_in_kb(args.db, kb_id):
                skipped += 1
                print("  already in KB", flush=True)
                continue

            result = add_to_kb(url, token, kb_id, file_id)
            if result == "added":
                added += 1
            elif result == "empty":
                skipped += 1
            else:
                skipped += 1
            print(f"  {result}", flush=True)
        except Exception as exc:
            failed += 1
            print(f"  FAILED: {exc}", flush=True)

        if args.pause:
            time.sleep(args.pause)

    print(
        f"done: added={added}, reused_upload={reused}, skipped={skipped}, failed={failed}",
        flush=True,
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
