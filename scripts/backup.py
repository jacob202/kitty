#!/usr/bin/env python3
"""
Kitty backup script — runs restic to back up data/ to local drive and Backblaze B2.

Usage:
    python scripts/backup.py                # both destinations
    python scripts/backup.py --local-only   # skip B2
    python scripts/backup.py --b2-only      # skip local drive
    python scripts/backup.py --dry-run      # preflight + connectivity check only
"""

import argparse
import logging
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("kitty.backup")

RESTIC_BIN = "/opt/homebrew/bin/restic"
DATA_DIR = str(PROJECT_ROOT / "data")
DEFAULT_LOCAL_PATH = "/Volumes/KittyBackup"


def check_filevault() -> bool:
    """Return True if FileVault is On. Returns False on any error."""
    try:
        result = subprocess.run(
            ["fdesetup", "status"],
            capture_output=True,
            text=True,
            check=False,
        )
        return "FileVault is On" in result.stdout
    except (FileNotFoundError, OSError):
        return False


def check_local_drive(mount_path: str | None = None) -> bool:
    """Return True if the external drive mount point exists."""
    path = mount_path or os.getenv("BACKUP_LOCAL_PATH", DEFAULT_LOCAL_PATH)
    return Path(path).is_dir()


def build_restic_env(repository: str) -> dict:
    """Build env dict for a restic subprocess. Raises EnvironmentError if password missing."""
    password = os.getenv("RESTIC_PASSWORD")
    if not password:
        raise EnvironmentError("RESTIC_PASSWORD is not set — cannot run restic")
    env = dict(os.environ)
    env["RESTIC_REPOSITORY"] = repository
    env["RESTIC_PASSWORD"] = password
    if b2_id := os.getenv("B2_ACCOUNT_ID"):
        env["B2_ACCOUNT_ID"] = b2_id
    if b2_key := os.getenv("B2_ACCOUNT_KEY"):
        env["B2_ACCOUNT_KEY"] = b2_key
    return env


def run_restic_backup(
    repository: str,
    source_path: str,
    extra_env: dict | None = None,
    dry_run: bool = False,
) -> subprocess.CompletedProcess:
    """Run restic backup. dry_run uses snapshots (read-only). Raises on failure."""
    env = extra_env or build_restic_env(repository)
    if dry_run:
        cmd = [RESTIC_BIN, "-r", repository, "snapshots"]
    else:
        cmd = [RESTIC_BIN, "-r", repository, "backup", source_path, "--verbose"]
    return subprocess.run(cmd, env=env, capture_output=True, text=True, check=True)


def run_restic_check(
    repository: str,
    extra_env: dict | None = None,
) -> subprocess.CompletedProcess:
    """Run restic check to verify repository integrity."""
    env = extra_env or build_restic_env(repository)
    cmd = [RESTIC_BIN, "-r", repository, "check"]
    return subprocess.run(cmd, env=env, capture_output=True, text=True, check=True)


def backup_local(dry_run: bool = False) -> bool:
    """Back up DATA_DIR to the local external drive. Returns True on success."""
    mount = os.getenv("BACKUP_LOCAL_PATH", DEFAULT_LOCAL_PATH)
    if not check_local_drive(mount):
        logger.warning("Local backup drive not mounted at %s — skipping", mount)
        return False
    repo = str(Path(mount) / "restic-repo")
    try:
        env = build_restic_env(repo)
        result = run_restic_backup(repo, DATA_DIR, extra_env=env, dry_run=dry_run)
        logger.info("Local backup complete: %s", result.stdout.strip().splitlines()[-1] if result.stdout else "ok")
        return True
    except (EnvironmentError, subprocess.CalledProcessError) as exc:
        logger.error("Local backup failed: %s", exc)
        return False


def backup_b2(dry_run: bool = False) -> bool:
    """Back up DATA_DIR to Backblaze B2. Returns True on success."""
    bucket = os.getenv("BACKUP_B2_BUCKET", "kitty-backup")
    repo = f"b2:{bucket}"
    try:
        env = build_restic_env(repo)
        result = run_restic_backup(repo, DATA_DIR, extra_env=env, dry_run=dry_run)
        logger.info("B2 backup complete: %s", result.stdout.strip().splitlines()[-1] if result.stdout else "ok")
        return True
    except (EnvironmentError, subprocess.CalledProcessError) as exc:
        logger.error("B2 backup failed: %s", exc)
        return False


def preflight_checks() -> list[str]:
    """Return list of warning strings. Empty = all clear."""
    warnings = []
    if not check_filevault():
        warnings.append("FileVault is Off — disk is not encrypted")
    if not (os.path.isfile(RESTIC_BIN) and os.access(RESTIC_BIN, os.X_OK)):
        warnings.append(f"restic not found at {RESTIC_BIN} — install with: brew install restic")
    if not os.getenv("RESTIC_PASSWORD"):
        warnings.append("RESTIC_PASSWORD is not set in .env")
    return warnings


def main(argv: list[str] | None = None) -> int:
    """Parse args, run preflight, run backups. Returns exit code."""
    parser = argparse.ArgumentParser(description="Kitty nightly backup via restic")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--local-only", action="store_true", help="Skip B2, only back up to external drive")
    group.add_argument("--b2-only", action="store_true", help="Skip local drive, only back up to B2")
    parser.add_argument("--dry-run", action="store_true", help="Check connectivity only, do not write data")
    args = parser.parse_args(argv)

    for warning in preflight_checks():
        logger.warning(warning)

    results = []
    if not args.b2_only:
        results.append(backup_local(dry_run=args.dry_run))
    if not args.local_only:
        results.append(backup_b2(dry_run=args.dry_run))

    success = all(results) if results else True
    if success:
        logger.info("Backup complete.")
    else:
        logger.error("One or more backup destinations failed.")
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
