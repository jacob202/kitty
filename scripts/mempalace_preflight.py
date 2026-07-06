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
import os
import shutil
import subprocess
import sys

# Make `gateway` importable no matter where this is run from.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

CANARY_QUERY = "kitty mempalace preflight canary"
OK = "\033[32m✓\033[0m"
NO = "\033[31m✗\033[0m"
WARN = "\033[33m!\033[0m"


def _print(symbol: str, msg: str) -> None:
    print(f"  {symbol} {msg}")


def check_python_import() -> bool:
    """Is the Python package importable? (Informational — adapter uses the CLI.)"""
    try:
        import mempalace  # noqa: F401

        _print(OK, "Python package `mempalace` is importable")
        return True
    except Exception as e:  # noqa: BLE001
        _print(WARN, f"Python package not importable ({e}). The adapter uses the "
                     f"CLI, so this is OK — but note it if you want the Python API.")
        return False


def check_cli_present() -> str | None:
    exe = shutil.which("mempalace")
    if exe:
        _print(OK, f"`mempalace` CLI on PATH: {exe}")
    else:
        _print(NO, "`mempalace` CLI not on PATH. Run `pip install mempalace` and "
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
        _print(WARN, "If the flags differ in your version, update both the search "
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
        _print(NO, f"expected a list (or {{'results': [...]}}), got {type(data).__name__}. "
                   "Adjust MemPalaceAdapter._parse().")
        return False

    _print(OK, f"search returns valid JSON ({len(rows)} row(s); empty is fine for a fresh store)")
    if rows and isinstance(rows[0], dict):
        keys = sorted(rows[0].keys())
        _print(OK if {"text", "content", "snippet"} & set(keys) else WARN,
               f"row keys: {keys}")
        has_rel = bool(rows[0].get("related") or rows[0].get("relations"))
        _print(OK if has_rel else WARN,
               f"typed-relationship field present: {has_rel} "
               f"(needed to finalize correlate(); paste a populated row to Claude)")
    return True


def main() -> int:
    print("\nMemPalace preflight\n" + "=" * 60)
    check_python_import()
    exe = check_cli_present()
    if not exe:
        print("\n" + "=" * 60)
        print(f"{NO} FAIL — install the CLI, then re-run. See "
              "docs/phases/MEMPALACE_MIGRATION_RUNBOOK.md")
        return 1
    dump_subcommands(exe)
    ok = check_search_shape(exe)
    print("\n" + "=" * 60)
    if ok:
        print(f"{OK} PASS — read path verified. Next: dry-run the migration "
              "(see docs/phases/MEMPALACE_MIGRATION_RUNBOOK.md, step 5).")
        return 0
    print(f"{NO} FAIL — fix the search shape above, then re-run.")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
