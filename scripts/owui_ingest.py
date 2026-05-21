#!/usr/bin/env python3
"""Upload staged chat history txt files to Open WebUI knowledge base.

Usage:
    python scripts/owui_ingest.py [--dirs DIR [DIR ...]] [--kb-id ID] [--url URL]

Defaults to all data/imports/ subdirs and the 'Chat History' KB.
Queries the Open WebUI SQLite DB directly to skip already-processed files
and reuse existing file IDs instead of re-uploading duplicate content.
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent

OWUI_URL = os.environ.get("OWUI_URL", "http://localhost:3001")
OWUI_EMAIL = os.environ.get("OWUI_EMAIL", "")
OWUI_PASSWORD = os.environ.get("OWUI_PASSWORD", "")
OWUI_DB = Path(
    os.environ.get(
        "OWUI_DB",
        str(
            Path.home()
            / "kitty-services/venv/lib/python3.12/site-packages/open_webui/data/webui.db"
        ),
    )
)

DEFAULT_DIRS = [
    ROOT / "data/imports/claude_export",
    ROOT / "data/imports/chatgpt",
    ROOT / "data/imports/claude_sessions",
]

CHAT_HISTORY_KB_ID = "bc62d700-93ca-403a-9163-06dbce6f061c"


def login(url: str, email: str, password: str) -> str:
    if not email or not password:
        sys.exit("Set OWUI_EMAIL and OWUI_PASSWORD before running this script.")
    resp = requests.post(
        f"{url}/api/v1/auths/signin",
        json={"email": email, "password": password},
        timeout=10,
    )
    resp.raise_for_status()
    token = resp.json().get("token")
    if not token:
        sys.exit("Login failed — check OWUI_EMAIL / OWUI_PASSWORD")
    return token


def db_state(db_path: Path, kb_id: str) -> tuple[dict[str, str], set[str]]:
    """Return (filename→file_id mapping for all uploaded files, set of file_ids already in KB)."""
    conn = sqlite3.connect(str(db_path))
    # Use the LATEST uploaded file for each filename (in case of duplicates)
    rows = conn.execute(
        "SELECT filename, id FROM file ORDER BY created_at ASC"
    ).fetchall()
    filename_to_id: dict[str, str] = {}
    for fname, fid in rows:
        filename_to_id[fname] = fid  # later rows overwrite, keeping newest

    in_kb = {
        r[0]
        for r in conn.execute(
            "SELECT file_id FROM knowledge_file WHERE knowledge_id=?", (kb_id,)
        ).fetchall()
    }
    conn.close()
    return filename_to_id, in_kb


def upload_file(url: str, token: str, path: Path) -> str | None:
    with open(path, "rb") as fh:
        resp = requests.post(
            f"{url}/api/v1/files/",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": (path.name, fh, "text/plain")},
            timeout=60,
        )
    if not resp.ok:
        print(f"UPLOAD FAILED ({resp.status_code})")
        return None
    return resp.json().get("id")


def add_to_kb(url: str, token: str, kb_id: str, file_id: str) -> str:
    """Returns 'ok', 'duplicate', or 'error'."""
    resp = requests.post(
        f"{url}/api/v1/knowledge/{kb_id}/file/add",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json={"file_id": file_id},
        timeout=30,
    )
    try:
        body = resp.json()
    except Exception:
        body = {}
    if resp.ok and "detail" not in body:
        return "ok"
    detail = str(body.get("detail", ""))
    if "Duplicate" in detail:
        return "duplicate"
    return "error"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dirs", nargs="+", type=Path, default=DEFAULT_DIRS)
    parser.add_argument("--kb-id", default=CHAT_HISTORY_KB_ID)
    parser.add_argument("--url", default=OWUI_URL)
    parser.add_argument("--batch-pause", type=float, default=0.2)
    args = parser.parse_args()

    token = login(args.url, OWUI_EMAIL, OWUI_PASSWORD)

    filename_to_id, in_kb_ids = db_state(OWUI_DB, args.kb_id)
    in_kb_names = {fname for fname, fid in filename_to_id.items() if fid in in_kb_ids}
    print(f"DB: {len(filename_to_id)} uploaded files, {len(in_kb_ids)} already in KB")

    files: list[Path] = []
    for d in args.dirs:
        if d.exists():
            files.extend(sorted(d.glob("*.txt")))
        else:
            print(f"Dir not found, skipping: {d}")

    to_process = [f for f in files if f.name not in in_kb_names]
    print(f"Files to process: {len(to_process)} / {len(files)} total\n")

    ok = skipped = failed = 0
    for i, path in enumerate(to_process, 1):
        print(f"[{i}/{len(to_process)}] {path.name}", end=" ... ", flush=True)

        # Reuse existing file ID if already uploaded
        file_id = filename_to_id.get(path.name)
        if file_id:
            print("(reusing existing ID)", end=" ", flush=True)
        else:
            file_id = upload_file(args.url, token, path)
            if not file_id:
                failed += 1
                print()
                continue

        result = add_to_kb(args.url, token, args.kb_id, file_id)
        if result == "ok":
            print("ok")
            ok += 1
        elif result == "duplicate":
            print("already embedded (counted as ok)")
            ok += 1
        else:
            print("KB add error")
            failed += 1

        if args.batch_pause:
            time.sleep(args.batch_pause)

    print(f"\nDone — added: {ok}, already in KB: {skipped}, failed: {failed}")


if __name__ == "__main__":
    main()
