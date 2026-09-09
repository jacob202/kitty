"""Local backup and restore drill for Kitty app-owned data."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from gateway.paths import DATA_DIR, KITTY_DATA_DIR, ROOT

DEFAULT_SOURCE_DIR = KITTY_DATA_DIR
DEFAULT_BACKUP_ROOT = DATA_DIR / "backups" / "kitty"
# Non-data owner inventory (config/...) belongs to the runtime checkout.
# Only data/... entries are remapped through DATA_DIR/KITTY_DATA_ROOT.
DEFAULT_OWNER_DATA_ROOT = ROOT

# Explicit owner-data inventory. This intentionally excludes secrets such as
# .env and data/gmail_token.json. Most structured owner stores share
# data/kitty/kitty.db; the remaining entries are canonical stores identified
# by the PAA-1 owner-memory classification audit, plus Builder's durable
# queue DB and the compute-governor and image stores.
#
# Deliberately excluded: the rest of data/kittybuilder/ (attempts/, runs/,
# reports/, backups/, ...) — Builder's per-attempt execution scratch, ~10GB
# on the canonical checkout. Only its durable queue DB is backed up here;
# including the scratch trees is a materially larger change (backup size and
# runtime), not a path-selection fix.
OWNER_DATA_RELATIVE_PATHS = (
    "data/kitty",
    "data/mem0",
    "data/session_consolidation_log.jsonl",
    "data/inbox.jsonl",
    "data/inbox_processed.jsonl",
    "data/captures",
    "data/knowledge_db",
    "data/inventory.csv",
    "data/web_monitors.db",
    "data/plugin_settings.json",
    "data/journal_entries.jsonl",
    "data/kittybuilder/builder_queue.db",
    "data/compute_governor",
    "data/images",
    "config/PREFERENCES.md",
    "config/user_profile.json",
    "config/USER",
)


_BUILDER_PROCESS_MARKERS = (
    "gateway.builder_supervisor",
    "gateway.builder_runner --supervise",
    "start_builder_supervisor.sh",
    "kittybuilder_dsh_worker.sh",
    "kittybuilder_dsh_reviewer.sh",
)


def _active_builder_processes() -> list[str]:
    """Return live Builder supervisor/worker process lines, or fail closed."""
    try:
        result = subprocess.run(
            ["ps", "-axo", "pid=,command="],
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RuntimeError(
            "Cannot verify Builder is quiescent; refusing owner-data restore"
        ) from exc

    current_pid = str(os.getpid())
    active: list[str] = []
    for line in result.stdout.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        pid = stripped.split(None, 1)[0]
        if pid == current_pid:
            continue
        if any(marker in stripped for marker in _BUILDER_PROCESS_MARKERS):
            active.append(stripped)
    return active


def _assert_builder_quiescent_for_restore() -> None:
    """Fail before replacing Builder queue or compute-governor live stores."""
    active = _active_builder_processes()
    if active:
        raise RuntimeError(
            "Kitty owner-data restore refuses to replace Builder/governor state "
            "while Builder is active; stop Builder first (active: "
            + "; ".join(active)
            + ")"
        )


def _prepare_builder_queue_replace(dest: Path, stamp: str) -> None:
    """Move the queue database and SQLite sidecars aside before replacement."""
    aside = dest.parent / f"{dest.name}.pre-restore-{stamp}"
    if aside.exists():
        raise RuntimeError(f"Kitty restore aside already exists: {aside}")
    if dest.exists():
        shutil.move(str(dest), str(aside))
    for suffix in ("-wal", "-shm"):
        sidecar = Path(str(dest) + suffix)
        if sidecar.exists():
            shutil.move(str(sidecar), str(aside) + suffix)

def _owner_path(project_root: Path, data_root: Path, relative: str) -> Path:
    if relative.startswith("data/"):
        return data_root / relative.removeprefix("data/")
    return project_root / relative




def create_backup(
    source_dir: Path = DEFAULT_SOURCE_DIR,
    backup_root: Path = DEFAULT_BACKUP_ROOT,
    timestamp: str | None = None,
) -> Path:
    source = Path(source_dir)
    if not source.exists():
        raise RuntimeError(f"Kitty backup source does not exist: {source}")
    if not source.is_dir():
        raise RuntimeError(f"Kitty backup source is not a directory: {source}")

    stamp = timestamp or _utc_stamp()
    destination = Path(backup_root) / stamp
    if destination.exists():
        raise RuntimeError(f"Kitty backup destination already exists: {destination}")

    destination.mkdir(parents=True)
    copied: list[str] = []
    try:
        for child in sorted(source.iterdir()):
            target = destination / child.name
            if child.is_dir():
                shutil.copytree(child, target)
            elif child.suffix == ".db":
                _backup_sqlite(child, target)
            else:
                shutil.copy2(child, target)
            copied.append(child.name)
        _write_manifest(destination, source, copied, stamp)
    except Exception:
        shutil.rmtree(destination, ignore_errors=True)
        raise
    return destination



def create_owner_backup(
    project_root: Path = DEFAULT_OWNER_DATA_ROOT,
    backup_root: Path = DEFAULT_BACKUP_ROOT,
    timestamp: str | None = None,
    *,
    data_root: Path | None = None,
) -> Path:
    """Back up every classified canonical owner-data path, excluding secrets.

    Paths are stored relative to the project root so the archive can be restored
    into a fresh installation without flattening unrelated stores together.
    Missing optional stores are recorded in the manifest rather than silently
    omitted.
    """
    root = Path(project_root)
    if not root.exists() or not root.is_dir():
        raise RuntimeError(f"Kitty project root does not exist: {root}")
    selected_data_root = (
        Path(data_root)
        if data_root is not None
        else (DATA_DIR if root == DEFAULT_OWNER_DATA_ROOT else root / "data")
    )
    # Without the canonical personal database the archive is not a backup of
    # Jacob's workspace: every store would be recorded "missing" and the command
    # would still exit successfully, which is how a restore silently loses data.
    personal_db = selected_data_root / "kitty" / "kitty.db"
    if not personal_db.is_file():
        raise RuntimeError(
            "Kitty owner-data backup refuses to publish without the canonical "
            f"personal database: {personal_db}"
        )

    stamp = timestamp or _utc_stamp()
    destination = Path(backup_root) / stamp
    if destination.exists():
        raise RuntimeError(f"Kitty backup destination already exists: {destination}")
    payload_root = destination / "owner-data"
    payload_root.mkdir(parents=True)

    copied: list[str] = []
    missing: list[str] = []
    try:
        for relative in OWNER_DATA_RELATIVE_PATHS:
            source = _owner_path(root, selected_data_root, relative)
            if not source.exists():
                missing.append(relative)
                continue
            target = payload_root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            _copy_path_sqlite_safe(source, target)
            copied.append(relative)
        manifest = {
            "schema_version": 2,
            "mode": "owner-data",
            "created_at": stamp,
            "source": str(root),
            "data_source": str(selected_data_root),
            "files": copied,
            "missing": missing,
            "excluded_secrets": [".env", "data/gmail_token.json"],
        }
        (destination / "backup_manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except Exception:
        shutil.rmtree(destination, ignore_errors=True)
        raise
    return destination


def restore_owner_backup(
    backup_dir: Path,
    target_root: Path,
    *,
    replace: bool = False,
    data_root: Path | None = None,
) -> Path:
    """Restore an owner-data archive into a project root or fresh-install root."""
    backup = Path(backup_dir)
    target = Path(target_root)
    selected_data_root = (
        Path(data_root)
        if data_root is not None
        else (DATA_DIR if target == DEFAULT_OWNER_DATA_ROOT else target / "data")
    )
    manifest_path = backup / "backup_manifest.json"
    if not manifest_path.is_file():
        raise RuntimeError(f"Not a Kitty backup archive (no backup_manifest.json): {backup}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("mode") != "owner-data":
        raise RuntimeError(f"Not a Kitty owner-data backup archive: {backup}")
    payload_root = backup / "owner-data"
    if not payload_root.is_dir():
        raise RuntimeError(f"Owner-data payload is missing: {payload_root}")

    files = list(manifest.get("files", []))
    queue_relative = "data/kittybuilder/builder_queue.db"
    governor_relative = "data/compute_governor"
    queue_dest = _owner_path(target, selected_data_root, queue_relative)
    queue_sidecars = [Path(str(queue_dest) + suffix) for suffix in ("-wal", "-shm")]
    governor_dest = _owner_path(target, selected_data_root, governor_relative)
    # The governor store is a live WAL database too, so a running Builder can be
    # mid-write there even when the queue DB is absent from the archive.
    protected_live_state = (
        queue_relative in files
        and (queue_dest.exists() or any(path.exists() for path in queue_sidecars))
    ) or (governor_relative in files and governor_dest.exists())
    if replace and protected_live_state:
        # This must happen before the restore loop moves *any* live owner data.
        _assert_builder_quiescent_for_restore()

    target.mkdir(parents=True, exist_ok=True)
    stamp = _utc_stamp()
    restored: list[Path] = []
    try:
        for relative in files:
            if relative not in OWNER_DATA_RELATIVE_PATHS:
                raise RuntimeError(f"Owner-data manifest contains unknown path: {relative}")
            source = payload_root / relative
            if not source.exists():
                raise RuntimeError(f"Owner-data archive is missing declared path: {relative}")
            dest = _owner_path(target, selected_data_root, relative)
            if dest.exists():
                if not replace:
                    raise RuntimeError(
                        f"Kitty owner-data restore target already exists: {dest} "
                        "(pass --replace to move it aside first)"
                    )
                if relative == "data/kittybuilder/builder_queue.db":
                    _prepare_builder_queue_replace(dest, stamp)
                else:
                    aside = dest.parent / f"{dest.name}.pre-restore-{stamp}"
                    if aside.exists():
                        raise RuntimeError(f"Kitty restore aside already exists: {aside}")
                    shutil.move(str(dest), str(aside))
            dest.parent.mkdir(parents=True, exist_ok=True)
            _copy_path_sqlite_safe(source, dest)
            restored.append(dest)
        _verify_restored_sqlite_paths(restored)
    except Exception:
        # A fresh-install drill should not leave a half-restored tree. For a
        # replace restore the moved-aside originals remain recoverable.
        for path in reversed(restored):
            if path.is_dir():
                shutil.rmtree(path, ignore_errors=True)
            else:
                path.unlink(missing_ok=True)
        raise
    return target


def _copy_path_sqlite_safe(source: Path, destination: Path) -> None:
    if source.is_dir():
        shutil.copytree(source, destination, copy_function=_copy_file_sqlite_safe)
    else:
        _copy_file_sqlite_safe(str(source), str(destination))


def _copy_file_sqlite_safe(source: str, destination: str) -> str:
    src = Path(source)
    dst = Path(destination)
    if src.suffix.lower() in {".db", ".sqlite", ".sqlite3"}:
        _backup_sqlite(src, dst)
    else:
        shutil.copy2(src, dst)
    return str(dst)


def _verify_restored_sqlite_paths(paths: list[Path]) -> None:
    bad: list[str] = []
    candidates: list[Path] = []
    for path in paths:
        if path.is_dir():
            candidates.extend(
                p for p in path.rglob("*")
                if p.is_file() and p.suffix.lower() in {".db", ".sqlite", ".sqlite3"}
            )
        elif path.suffix.lower() in {".db", ".sqlite", ".sqlite3"}:
            candidates.append(path)
    for db in sorted(set(candidates)):
        try:
            with sqlite3.connect(db) as conn:
                row = conn.execute("PRAGMA integrity_check").fetchone()
            if row is None or row[0] != "ok":
                bad.append(f"{db}: integrity_check != ok")
        except sqlite3.Error as exc:
            bad.append(f"{db}: {exc}")
    if bad:
        raise RuntimeError("Restored SQLite failed integrity check:\n" + "\n".join(bad))

def restore_drill(backup_dir: Path, restore_dir: Path) -> Path:
    """Copy a backup into a brand-new directory (dry-run restore).

    Kept as the non-destructive drill; the real restore path is ``restore``.
    """
    backup = Path(backup_dir)
    target = Path(restore_dir)
    if not backup.exists():
        raise RuntimeError(f"Kitty restore backup does not exist: {backup}")
    if not backup.is_dir():
        raise RuntimeError(f"Kitty restore backup is not a directory: {backup}")
    if target.exists():
        raise RuntimeError(f"Kitty restore target already exists: {target}")

    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(backup, target)
    return target


def restore(
    backup_dir: Path,
    target_dir: Path | None = None,
    replace: bool = False,
) -> Path:
    """Restore a Kitty backup archive into ``target_dir`` in place.

    Fail-loud guards, never silent fallbacks:

    - The backup must be a real Kitty archive: it must exist, be a directory,
      and carry ``backup_manifest.json``. Restoring an arbitrary directory is
      refused rather than guessed at.
    - An existing non-empty target is refused unless ``replace`` is set, in
      which case the existing target is moved aside (never deleted) to
      ``<target>.pre-restore-<stamp>``.
    - After the copy, every restored ``*.db`` file must pass SQLite's
      ``PRAGMA integrity_check``. A restored archive whose databases do not
      open cleanly raises, so a corrupt restore cannot masquerade as success.
    """
    backup = Path(backup_dir)
    if not backup.exists():
        raise RuntimeError(f"Kitty restore backup does not exist: {backup}")
    if not backup.is_dir():
        raise RuntimeError(f"Kitty restore backup is not a directory: {backup}")
    manifest_path = backup / "backup_manifest.json"
    if not manifest_path.is_file():
        raise RuntimeError(f"Not a Kitty backup archive (no backup_manifest.json): {backup}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("mode") == "owner-data":
        target_root = Path(target_dir) if target_dir is not None else DEFAULT_OWNER_DATA_ROOT
        selected_data_root = None if target_dir is not None else DATA_DIR
        return restore_owner_backup(
            backup, target_root, replace=replace, data_root=selected_data_root
        )

    target = Path(target_dir) if target_dir is not None else DEFAULT_SOURCE_DIR
    if target.exists() and any(target.iterdir()):
        if not replace:
            raise RuntimeError(
                f"Kitty restore target is not empty: {target} "
                "(pass --replace to move the existing target aside first)"
            )
        aside = target.parent / f"{target.name}.pre-restore-{_utc_stamp()}"
        shutil.move(str(target), str(aside))

    target.mkdir(parents=True, exist_ok=True)
    try:
        for child in sorted(backup.iterdir()):
            if child.name == "backup_manifest.json":
                continue
            dest = target / child.name
            if child.is_dir():
                shutil.copytree(child, dest, dirs_exist_ok=True)
            else:
                shutil.copy2(child, dest)
        _verify_restored_sqlite(target)
    except Exception:
        shutil.rmtree(target, ignore_errors=True)
        raise
    return target


def _verify_restored_sqlite(target_dir: Path) -> None:
    bad: list[str] = []
    for db in sorted(target_dir.rglob("*.db")):
        try:
            with sqlite3.connect(db) as conn:
                row = conn.execute("PRAGMA integrity_check").fetchone()
            if row is None or row[0] != "ok":
                bad.append(f"{db}: integrity_check != ok")
        except sqlite3.Error as exc:
            bad.append(f"{db}: {exc}")
    if bad:
        raise RuntimeError("Restored SQLite failed integrity check:\n" + "\n".join(bad))


def _backup_sqlite(source: Path, destination: Path) -> None:
    try:
        with sqlite3.connect(source) as src, sqlite3.connect(destination) as dst:
            src.backup(dst)
    except sqlite3.Error as exc:
        raise RuntimeError(f"SQLite backup failed from {source} to {destination}: {exc}") from exc


def _write_manifest(
    destination: Path,
    source: Path,
    copied: list[str],
    stamp: str,
) -> None:
    manifest = {
        "created_at": stamp,
        "source": str(source),
        "files": copied,
    }
    (destination / "backup_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="command", required=True)

    backup = subcommands.add_parser("backup", help="Back up canonical owner data")
    backup.add_argument(
        "--source-dir",
        type=Path,
        default=None,
        help="legacy single-directory backup; omitted means canonical owner-data backup",
    )
    backup.add_argument("--backup-root", type=Path, default=DEFAULT_BACKUP_ROOT)

    drill = subcommands.add_parser(
        "restore-drill",
        help="Restore a backup into a new directory for verification",
    )
    drill.add_argument("backup_dir", type=Path)
    drill.add_argument("restore_dir", type=Path)

    real_restore = subcommands.add_parser(
        "restore",
        help="Restore a backup archive into the live data directory",
    )
    real_restore.add_argument("backup_dir", type=Path)
    real_restore.add_argument(
        "--target-dir",
        type=Path,
        default=None,
        help="restore root; defaults to the selected personal workspace for owner-data backups and data/kitty for legacy backups",
    )
    real_restore.add_argument(
        "--replace",
        action="store_true",
        help="move the existing non-empty target aside before restoring",
    )

    args = parser.parse_args(argv)
    if args.command == "backup":
        if args.source_dir is None:
            destination = create_owner_backup(backup_root=args.backup_root)
        else:
            destination = create_backup(args.source_dir, args.backup_root)
        print(destination)
        return 0
    if args.command == "restore-drill":
        destination = restore_drill(args.backup_dir, args.restore_dir)
        print(destination)
        return 0
    if args.command == "restore":
        destination = restore(args.backup_dir, args.target_dir, replace=args.replace)
        print(destination)
        return 0
    raise RuntimeError(f"Unknown kitty_backup command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
