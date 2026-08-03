"""Local backup and restore drill for Kitty app-owned data."""

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from gateway.paths import DATA_DIR, KITTY_DATA_DIR

DEFAULT_SOURCE_DIR = KITTY_DATA_DIR
DEFAULT_BACKUP_ROOT = DATA_DIR / "backups" / "kitty"


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
    target_dir: Path = DEFAULT_SOURCE_DIR,
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
    target = Path(target_dir)
    if not backup.exists():
        raise RuntimeError(f"Kitty restore backup does not exist: {backup}")
    if not backup.is_dir():
        raise RuntimeError(f"Kitty restore backup is not a directory: {backup}")
    if not (backup / "backup_manifest.json").is_file():
        raise RuntimeError(f"Not a Kitty backup archive (no backup_manifest.json): {backup}")

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

    backup = subcommands.add_parser("backup", help="Back up data/kitty")
    backup.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE_DIR)
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
        default=DEFAULT_SOURCE_DIR,
        help="directory to restore into (default: data/kitty)",
    )
    real_restore.add_argument(
        "--replace",
        action="store_true",
        help="move the existing non-empty target aside before restoring",
    )

    args = parser.parse_args(argv)
    if args.command == "backup":
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
