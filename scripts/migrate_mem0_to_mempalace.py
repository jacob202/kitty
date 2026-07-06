#!/usr/bin/env python3
"""Migrate Kitty's mem0 memories into MemPalace — safely and idempotently.

Design guarantees (so re-running or aborting is never scary):
  * DRY-RUN BY DEFAULT. Nothing is written until you pass --execute.
  * NON-DESTRUCTIVE. mem0 data is never modified or deleted; MemPalace is
    additive and off-by-default, so rollback is just `unset KITTY_MEMPALACE_ENABLED`.
  * BACKS UP first (copies data/mem0) before --execute, unless --no-backup.
  * IDEMPOTENT. A manifest (data/mempalace_migration_state.json) records which
    memory ids were migrated; re-runs skip them, so an interrupted run resumes.
  * The ONE unverified call (how MemPalace ingests text) is isolated in one
    function and overridable with --ingest-cmd, so you never edit code blind.

Read the runbook first: docs/phases/MEMPALACE_MIGRATION_RUNBOOK.md

Typical use:
    python scripts/mempalace_preflight.py            # 1. verify the package
    python scripts/migrate_mem0_to_mempalace.py      # 2. dry-run (writes nothing)
    python scripts/migrate_mem0_to_mempalace.py --execute --ingest-cmd "mempalace add"
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Iterable, Optional

# Make `gateway` importable no matter where this is run from.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

DEFAULT_INGEST_CMD = "mempalace add"  # confirm via preflight `--help`; override with --ingest-cmd


# --- Pure, testable helpers (no MemPalace / mem0 imports at module load) ---


def normalize_memory(raw: Any) -> Optional[dict[str, Any]]:
    """mem0 record -> {id, text, namespace, metadata}, or None if it has no text.

    A stable id (mem0's own id, else a content hash) drives idempotency.
    """
    if not isinstance(raw, dict):
        return None
    text = (raw.get("memory") or raw.get("text") or raw.get("content") or "").strip()
    if not text:
        return None
    meta = raw.get("metadata") or {}
    mid = raw.get("id") or raw.get("memory_id")
    if not mid:
        mid = "sha1:" + hashlib.sha1(text.encode("utf-8")).hexdigest()
    return {
        "id": str(mid),
        "text": text,
        "namespace": meta.get("namespace", "facts"),
        "metadata": meta,
    }


def load_manifest(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"migrated_ids": [], "runs": []}


def save_manifest(path: Path, manifest: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")


def migrate(
    memories: Iterable[Any],
    ingest_fn: Callable[[str, dict[str, Any]], None],
    manifest: dict[str, Any],
    *,
    dry_run: bool = True,
    log: Callable[[str], None] = print,
) -> dict[str, int]:
    """Core loop. Pure logic + injected ingest_fn — fully unit-testable.

    Mutates ``manifest['migrated_ids']`` only for items actually ingested.
    """
    migrated_ids = set(manifest.get("migrated_ids", []))
    s = {"total": 0, "would_migrate": 0, "migrated": 0, "skipped": 0, "failed": 0, "empty": 0}
    for raw in memories:
        s["total"] += 1
        item = normalize_memory(raw)
        if item is None:
            s["empty"] += 1
            continue
        if item["id"] in migrated_ids:
            s["skipped"] += 1
            continue
        if dry_run:
            s["would_migrate"] += 1
            log(f"  would migrate [{item['namespace']}] {item['text'][:70]}")
            continue
        try:
            ingest_fn(item["text"], item["metadata"])
            migrated_ids.add(item["id"])
            s["migrated"] += 1
            log(f"  migrated [{item['namespace']}] {item['text'][:70]}")
        except Exception as e:  # noqa: BLE001 — one bad item must not abort the run
            s["failed"] += 1
            log(f"  FAILED {item['id']}: {e}")
    manifest["migrated_ids"] = sorted(migrated_ids)
    return s


# --- Side-effecting pieces (used only by main / --execute) ---


def make_cli_ingest(ingest_cmd: str) -> Callable[[str, dict[str, Any]], None]:
    """Build the ingest function from a CLI command string (e.g. 'mempalace add').

    This is the ONE call that depends on MemPalace's real API. If your version
    uses a different subcommand, just pass --ingest-cmd; no code change needed.
    """
    argv_base = ingest_cmd.split()
    exe = shutil.which(argv_base[0])
    if not exe:
        raise SystemExit(
            f"'{argv_base[0]}' not on PATH. Install MemPalace and run the preflight first."
        )

    def _ingest(text: str, metadata: dict[str, Any]) -> None:
        proc = subprocess.run(
            [exe, *argv_base[1:], text], capture_output=True, text=True, timeout=60
        )
        if proc.returncode != 0:
            raise RuntimeError(f"rc={proc.returncode}: {proc.stderr.strip()[:200]}")

    return _ingest


def backup_mem0(data_dir: Path) -> Optional[Path]:
    if not data_dir.exists():
        return None
    stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = data_dir.parent / f"mem0_backup_{stamp}"
    shutil.copytree(data_dir, dest)
    return dest


def load_source_memories(limit: int) -> list[dict[str, Any]]:
    """Read every stored mem0 memory through the clean public interface."""
    from gateway import memory  # lazy: keeps this script importable without mem0

    mems = memory.list_memories(limit=limit)
    if not mems:
        print("  (no memories returned — is mem0 installed and is the embedder up?)")
    return mems


def main(argv: Optional[list[str]] = None) -> int:
    from gateway.paths import DATA_DIR

    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--execute", action="store_true", help="actually migrate (default: dry-run)")
    p.add_argument("--ingest-cmd", default=DEFAULT_INGEST_CMD,
                   help=f"MemPalace ingest command (default: {DEFAULT_INGEST_CMD!r}). "
                        "Set this from the preflight's `--help` output.")
    p.add_argument("--no-backup", action="store_true", help="skip the data/mem0 backup")
    p.add_argument("--limit", type=int, default=100000, help="max memories to read")
    p.add_argument("--manifest", default=str(DATA_DIR / "mempalace_migration_state.json"))
    args = p.parse_args(argv)

    manifest_path = Path(args.manifest)
    manifest = load_manifest(manifest_path)
    mode = "EXECUTE" if args.execute else "DRY-RUN"
    print(f"\nmem0 → MemPalace migration [{mode}]\n" + "=" * 60)
    if manifest["migrated_ids"]:
        print(f"  resuming: {len(manifest['migrated_ids'])} already migrated (will skip)")

    if args.execute and not args.no_backup:
        dest = backup_mem0(DATA_DIR / "mem0")
        print(f"  backup: {dest}" if dest else "  backup: (no data/mem0 dir to back up)")

    ingest_fn: Callable[[str, dict[str, Any]], None]
    if args.execute:
        ingest_fn = make_cli_ingest(args.ingest_cmd)
    else:
        def ingest_fn(_t, _m):  # noqa: ANN001 — never called in dry-run
            raise AssertionError("ingest must not run during dry-run")

    memories = load_source_memories(args.limit)
    summary = migrate(memories, ingest_fn, manifest, dry_run=not args.execute)

    if args.execute:
        manifest["runs"].append({"at": _dt.datetime.now().isoformat(timespec="seconds"), **summary})
        save_manifest(manifest_path, manifest)

    print("\n" + "-" * 60)
    print(f"  summary: {summary}")
    if not args.execute:
        print("  dry-run only — nothing written. Re-run with --execute when ready.")
    else:
        print(f"  manifest: {manifest_path}")
        print("  verify: re-run scripts/mempalace_preflight.py, or search a known fact "
              "in the running app.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
