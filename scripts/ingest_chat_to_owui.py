#!/usr/bin/env python3
"""Upload converted chat history files into Open WebUI's Chat History KB.

Usage:
    python scripts/ingest_chat_to_owui.py [--workers N] [--dry-run] [--clean-dupes]
"""

from __future__ import annotations
import argparse, sys, time, sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import requests

WEBUI_URL = "http://127.0.0.1:3001"
EMAIL = "jacobbrizinski@gmail.com"
PASSWORD = "1234"
CHAT_HISTORY_KB_ID = "06435ea5-62e5-4272-ad37-9ad8a37434cc"
DB_PATH = Path.home() / "kitty-services/open-webui-data/webui.db"

CHAT_DIRS = [
    Path.home() / "Projects/kitty/data/imports/chatgpt",
    Path.home() / "Projects/kitty/data/imports/claude_export",
]


def get_token() -> str:
    r = requests.post(
        f"{WEBUI_URL}/api/v1/auths/signin",
        json={"email": EMAIL, "password": PASSWORD},
        timeout=10,
    )
    r.raise_for_status()
    return r.json()["token"]


def get_existing_files_from_db() -> dict[str, str]:
    """Get filename -> file_id mapping from webui.db to avoid duplicate uploads."""
    if not DB_PATH.exists():
        return {}
    conn = sqlite3.connect(str(DB_PATH))
    try:
        rows = conn.execute("SELECT filename, id FROM file ORDER BY created_at ASC").fetchall()
    finally:
        conn.close()
    return {row[0]: row[1] for row in rows}


def get_files_in_kb() -> set[str]:
    """Get set of file_ids already in the Chat History KB."""
    if not DB_PATH.exists():
        return set()
    conn = sqlite3.connect(str(DB_PATH))
    try:
        rows = conn.execute(
            "SELECT file_id FROM knowledge_file WHERE knowledge_id=?",
            (CHAT_HISTORY_KB_ID,),
        ).fetchall()
    finally:
        conn.close()
    return {row[0] for row in rows}


def upload_file(token: str, path: Path) -> str | None:
    with open(path, "rb") as f:
        r = requests.post(
            f"{WEBUI_URL}/api/v1/files/",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": (path.name, f, "text/plain")},
            timeout=30,
        )
    if r.status_code == 200:
        return r.json().get("id")
    print(
        f"  UPLOAD FAIL {r.status_code} {path.name[:50]}: {r.text[:80]}",
        file=sys.stderr,
    )
    return None


def add_to_kb(token: str, file_id: str) -> bool:
    r = requests.post(
        f"{WEBUI_URL}/api/v1/knowledge/{CHAT_HISTORY_KB_ID}/file/add",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json={"file_id": file_id},
        timeout=60,
    )
    if r.status_code == 200:
        return True
    text = r.text[:80]
    if "Duplicate" in text or "already" in text.lower():
        return True  # already embedded
    print(f"  KB FAIL {r.status_code}: {text}", file=sys.stderr)
    return False


def process_file(token: str, path: Path, existing_files: dict[str, str], kb_files: set[str], dry_run: bool) -> tuple[bool, str, str]:
    """Returns (success, filename, action)"""
    if dry_run:
        return True, path.name, "dry-run"

    # Check if file already uploaded
    file_id = existing_files.get(path.name)
    action = "reused" if file_id else "uploaded"

    if not file_id:
        file_id = upload_file(token, path)
        if not file_id:
            return False, path.name, "upload-fail"

    # Check if already in KB
    if file_id in kb_files:
        return True, path.name, "already-in-kb"

    ok = add_to_kb(token, file_id)
    return ok, path.name, "added" if ok else "kb-fail"


def clean_dupes(token: str) -> None:
    """Remove duplicate files from the database, keeping the oldest copy."""
    if not DB_PATH.exists():
        print("No database found to clean.")
        return

    conn = sqlite3.connect(str(DB_PATH))
    try:
        # Find duplicate filenames
        dupes = conn.execute(
            "SELECT filename, GROUP_CONCAT(id), COUNT(*) as cnt "
            "FROM file GROUP BY filename HAVING cnt > 1"
        ).fetchall()

        if not dupes:
            print("No duplicates found.")
            return

        print(f"Found {len(dupes)} duplicate filenames to clean...")
        removed = 0
        for filename, ids_str, cnt in dupes:
            ids = ids_str.split(",")
            # Keep the first (oldest) ID, remove the rest
            keep_id = ids[0]
            for dupe_id in ids[1:]:
                # Remove from knowledge_file first
                conn.execute("DELETE FROM knowledge_file WHERE file_id=?", (dupe_id,))
                # Remove the file
                conn.execute("DELETE FROM file WHERE id=?", (dupe_id,))
                removed += 1
        conn.commit()
        print(f"Removed {removed} duplicate files, kept {len(dupes)} originals.")
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--clean-dupes", action="store_true")
    args = parser.parse_args()

    if args.clean_dupes:
        print("Cleaning duplicate files...")
        clean_dupes(get_token())
        return

    print("Authenticating...")
    token = get_token()

    # Get existing files to avoid duplicates
    existing_files = get_existing_files_from_db()
    kb_files = get_files_in_kb()
    print(f"  Existing files in DB: {len(existing_files)}")
    print(f"  Files already in KB: {len(kb_files)}")

    # Collect all chat files
    all_files: list[Path] = []
    for d in CHAT_DIRS:
        if d.exists():
            files = sorted(d.glob("*.txt")) + sorted(d.glob("*.md"))
            print(f"  {d.name}: {len(files)} files")
            all_files.extend(files)
        else:
            print(f"  WARNING: {d} not found", file=sys.stderr)

    print(f"\nTotal: {len(all_files)} files to process")

    if args.dry_run:
        print("[dry-run] Done.")
        return

    total = len(all_files)
    done = ok_count = error_count = 0
    start = time.time()
    actions = {"uploaded": 0, "reused": 0, "already-in-kb": 0, "added": 0, "kb-fail": 0, "upload-fail": 0, "dry-run": 0}

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(process_file, token, p, existing_files, kb_files, args.dry_run): p for p in all_files}
        for fut in as_completed(futs):
            done += 1
            ok, name, action = fut.result()
            actions[action] = actions.get(action, 0) + 1
            if ok:
                ok_count += 1
            else:
                error_count += 1
            if done % 25 == 0 or done == total:
                elapsed = time.time() - start
                rate = done / elapsed
                remaining = (total - done) / rate if rate > 0 else 0
                print(
                    f"  {done}/{total} done  ok={ok_count} err={error_count}  "
                    f"~{remaining:.0f}s remaining"
                )

    print(f"\nDone. {ok_count} ok, {error_count} errors in {time.time()-start:.1f}s")
    print(f"Actions: {actions}")


if __name__ == "__main__":
    main()
