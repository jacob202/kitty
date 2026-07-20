#!/usr/bin/env python3
"""MemPalace preflight — prove the installed package before you trust it.

The MemPalace adapter (`gateway/mempalace_adapter.py`) and the migration script
were written WITHOUT a MemPalace package available to test against. This script
is the safety net: run it first, on your machine, with `mempalace` installed.
It confirms the read path the adapter depends on and surfaces the real CLI
subcommand names you'll need for ingestion — so nothing downstream is a guess.

Read-only by default (never writes to your store). Usage:

    pip install mempalace
    python scripts/mempalace_preflight.py

Exit code 0 = the search/read path is verified. Non-zero = fix before migrating.
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import sys

# Make `gateway` importable no matter where this is run from.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

logger = logging.getLogger("scripts.mempalace_preflight")
# Idempotent basicConfig: do not overwrite if the caller already wired logs
# (e.g. a future pytest or `--log-level` invocation).
if not logging.getLogger().handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

CANARY_QUERY = "kitty mempalace preflight canary"
OK = "\033[32m✓\033[0m"
NO = "\033[31m✗\033[0m"
WARN = "\033[33m!\033[0m"

# Default level so the existing 2-arg call sites keep working; callers can
# pass an explicit level via the (symbol, level, msg) form.
_DEFAULT_LEVEL_FOR_SYMBOL: dict[str, int] = {
    OK: logging.INFO,
    NO: logging.ERROR,
    WARN: logging.WARNING,
}


def _print(symbol: str, msg_or_level: object, msg: str | None = None) -> None:
    """Emit a colored status line to stdout AND the log.

    Backwards-compatible: ``_print(OK, "msg")`` still works (defaults the
    level from ``_DEFAULT_LEVEL_FOR_SYMBOL``), and the explicit
    ``_print(OK, logging.INFO, "msg")`` form is preferred for new call sites.
    """
    log_level: int
    if msg is None and isinstance(msg_or_level, str):
        log_level = _DEFAULT_LEVEL_FOR_SYMBOL.get(symbol, logging.INFO)
        line = f"  {symbol} {msg_or_level}"
    else:
        log_level = int(msg_or_level)  # type: ignore[arg-type]
        assert isinstance(msg, str)
        line = f"  {symbol} {msg}"
    print(line)
    logger.log(log_level, line)


def check_python_import() -> bool:
    """Is the Python package importable? (Informational — adapter uses the CLI.)"""
    try:
        import mempalace  # noqa: F401

        _print(OK, "Python package `mempalace` is importable")
        return True
    except Exception as e:  # noqa: BLE001
        _print(WARN,
               f"Python package not importable ({e}). The adapter uses the "
               f"CLI, so this is OK — but note it if you want the Python API.")
        return False


def check_cli_present() -> str | None:
    exe = shutil.which("mempalace")
    if exe:
        _print(OK, f"`mempalace` CLI on PATH: {exe}")
    else:
        _print(NO,
               "`mempalace` CLI not on PATH. Run `pip install mempalace` and "
               "ensure your venv's bin/ is active.")
    return exe


def dump_subcommands(exe: str) -> None:
    """Print the real CLI surface so the ingest subcommand name is never a guess."""
    try:
        proc = subprocess.run([exe, "--help"], capture_output=True, text=True, timeout=15)
        print("\n  --- `mempalace --help` (use this to set --ingest-cmd) ---")
        for line in (proc.stdout or proc.stderr).splitlines():
            print(f"  | {line}")
        print("  ---------------------------------------------------------")
    except Exception as e:  # noqa: BLE001
        _print(WARN, f"Could not read `mempalace --help`: {e}")


def check_search_shape(exe: str) -> bool:
    """Run a real search and validate it against what `MemPalaceAdapter._parse` expects."""
    try:
        proc = subprocess.run(
            [exe, "search", CANARY_QUERY, "--limit", "5", "--json"],
            capture_output=True, text=True, timeout=15,
        )
    except Exception as e:  # noqa: BLE001
        _print(NO, f"`mempalace search ... --json` failed to run: {e}")
        return False

    if proc.returncode != 0:
        _print(NO, f"search exited rc={proc.returncode}: {proc.stderr[:200]}")
        _print(WARN,
               "If the flags differ in your version, update both the search "
               "args here and in MemPalaceAdapter._search().")
        return False

    raw = proc.stdout.strip()
    print(f"\n  --- raw search JSON (first 500 chars) ---\n  {raw[:500]}\n  ---")
    try:
        data = json.loads(raw or "[]")
    except json.JSONDecodeError:
        _print(NO, "search output is not valid JSON. Adjust _search()/_parse().")
        return False

    rows = data.get("results", data) if isinstance(data, dict) else data
    if not isinstance(rows, list):
        _print(NO,
               f"expected a list (or {{'results': [...]}}), got {type(data).__name__}. "
               "Adjust MemPalaceAdapter._parse().")
        return False

    _print(OK,
           f"search returns valid JSON ({len(rows)} row(s); empty is fine for a fresh store)")
    if rows and isinstance(rows[0], dict):
        keys = sorted(rows[0].keys())
        has_content_key = bool({"text", "content", "snippet"} & set(keys))
        _print(OK if has_content_key else WARN, f"row keys: {keys}")
        has_rel = bool(rows[0].get("related") or rows[0].get("relations"))
        _print(OK if has_rel else WARN,
               f"typed-relationship field present: {has_rel} "
               f"(needed to finalize correlate(); paste a populated row to Claude)")
    return True


def main() -> int:
    logger.info("MemPalace preflight started")
    print("\nMemPalace preflight\n" + "=" * 60)
    check_python_import()
    exe = check_cli_present()
    if not exe:
        print("\n" + "=" * 60)
        print(f"{NO} FAIL — install the CLI, then re-run. See "
              "docs/phases/MEMPALACE_MIGRATION_RUNBOOK.md")
        logger.error("MemPalace preflight FAILED: CLI not installed")
        return 1
    dump_subcommands(exe)
    ok = check_search_shape(exe)
    print("\n" + "=" * 60)
    if ok:
        print(f"{OK} PASS — read path verified. Next: dry-run the migration "
              "(see docs/phases/MEMPALACE_MIGRATION_RUNBOOK.md, step 5).")
        logger.info("MemPalace preflight PASS — read path verified")
        return 0
    print(f"{NO} FAIL — fix the search shape above, then re-run.")
    logger.error("MemPalace preflight FAILED — search shape wrong")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
