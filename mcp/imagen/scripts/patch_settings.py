"""Idempotent JSON merger for MCP server config files.

Usage:
    echo '<server-entry-json>' | python3 patch_settings.py <path> <server-name> [--force] [--keep-existing]

Writes <server-name> under the `mcpServers` key in <path>. Both Claude Code
project files (.mcp.json) and the user-global file (~/.claude/settings.json)
use the same `mcpServers` key schema, so this script handles either.

Behavior:
  - File missing             -> created with the new entry
  - File exists, key absent  -> entry added, other top-level keys preserved
  - File exists, key equal   -> no-op, exit 0 (already configured)
  - File exists, key differs -> overwritten with --force (default), preserved
                                with --keep-existing; warning printed either way
  - File exists, malformed   -> exit 1, file untouched, .bak preserved

A timestamped .bak is written before any mutation. The original file is left
untouched on any error path (fail loud, never mask).
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path


def _load_or_empty(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"error: {path} is not valid JSON: {e}", file=sys.stderr)
        raise SystemExit(1)
    if not isinstance(data, dict):
        print(f"error: {path} top-level is not an object", file=sys.stderr)
        raise SystemExit(1)
    return data


def _round_trip(data: dict, path: Path) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=False)
        f.write("\n")
    try:
        with tmp.open("r", encoding="utf-8") as f:
            json.load(f)
    except json.JSONDecodeError as e:
        tmp.unlink(missing_ok=True)
        print(f"error: round-trip parse failed: {e}", file=sys.stderr)
        raise SystemExit(1)
    shutil.move(str(tmp), str(path))


def _read_stdin_config() -> dict:
    raw = sys.stdin.read().strip()
    if not raw:
        print("error: no config supplied on stdin", file=sys.stderr)
        raise SystemExit(2)
    try:
        cfg = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"error: config on stdin is not valid JSON: {e}", file=sys.stderr)
        raise SystemExit(2)
    if not isinstance(cfg, dict):
        print("error: config on stdin must be a JSON object", file=sys.stderr)
        raise SystemExit(2)
    return cfg


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("path", help="path to .mcp.json or settings.json")
    parser.add_argument("name", help="server name (e.g. imagen)")
    parser.add_argument("--force", action="store_true", default=True, help="overwrite if exists with different config (default)")
    parser.add_argument("--keep-existing", action="store_true", help="preserve existing config on mismatch")
    args = parser.parse_args()

    target = Path(args.path).expanduser()
    new_cfg = _read_stdin_config()

    existing = _load_or_empty(target)
    servers = existing.setdefault("mcpServers", {})
    if not isinstance(servers, dict):
        print(f"error: {target} 'mcpServers' is not an object", file=sys.stderr)
        return 1

    if args.name in servers:
        if servers[args.name] == new_cfg:
            print(f"ok: {args.name!r} already configured in {target}; no changes")
            return 0
        if args.keep_existing:
            print(f"warn: {args.name!r} differs in {target}; --keep-existing, leaving as-is", file=sys.stderr)
            return 0
        print(f"warn: {args.name!r} differs in {target}; overwriting", file=sys.stderr)

    if target.exists():
        backup = target.with_suffix(target.suffix + f".bak.{int(time.time())}")
        shutil.copyfile(target, backup)
        print(f"backup: {backup}")

    servers[args.name] = new_cfg
    _round_trip(existing, target)
    print(f"ok: wrote {args.name!r} to {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
