#!/usr/bin/env python3
"""Kitty gateway preflight/health doctor."""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import ssl
import urllib.request
from dataclasses import dataclass
from typing import Any


ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent
MANIFEST_FILE = ROOT_DIR / "gateway" / "runtime_manifest.json"


@dataclass
class CheckResult:
    level: str  # PASS|WARN|FAIL
    name: str
    detail: str


def http_json(
    url: str,
    method: str = "GET",
    body: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 4.0,
) -> tuple[int, dict[str, Any] | list[Any] | str]:
    data = None
    req_headers = {"Content-Type": "application/json"}
    if headers:
        req_headers.update(headers)
    if body is not None:
        data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url=url, data=data, headers=req_headers, method=method)
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
        code = resp.getcode()
        raw = resp.read().decode("utf-8", errors="replace")
        if not raw:
            return code, ""
        try:
            return code, json.loads(raw)
        except json.JSONDecodeError:
            return code, raw


def http_ok(url: str, timeout: float = 3.0, headers: dict[str, str] | None = None) -> bool:
    try:
        code, _ = http_json(url, timeout=timeout, headers=headers)
        return 200 <= code < 400
    except Exception:
        return False


def level_order(level: str) -> int:
    return {"PASS": 0, "WARN": 1, "FAIL": 2}.get(level, 2)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true", help="alias for --fail-on-warn")
    parser.add_argument("--fail-on-warn", action="store_true", help="return non-zero on WARN/FAIL")
    parser.add_argument("--json", action="store_true", help="emit JSON output")
    args = parser.parse_args()

    results: list[CheckResult] = []

    if not MANIFEST_FILE.exists():
        print(f"FAIL manifest missing: {MANIFEST_FILE}")
        return 2
    manifest = json.loads(MANIFEST_FILE.read_text(encoding="utf-8"))
    env = dict(os.environ)

    for rel in manifest.get("required_files", []):
        path = ROOT_DIR / rel
        if path.exists():
            results.append(CheckResult("PASS", f"file:{rel}", "present"))
        else:
            results.append(CheckResult("FAIL", f"file:{rel}", "missing"))

    for svc in manifest.get("services", []):
        svc_id = svc.get("id", "unknown")
        url = svc.get("url", "")
        required = bool(svc.get("required", False))
        headers = None
        timeout = 3.0
        if svc_id == "litellm":
            headers = {"Authorization": f"Bearer {env.get('LITELLM_MASTER_KEY', 'kitty-local-key-change-me')}"}
            timeout = 8.0
        ok = bool(url) and http_ok(url, timeout=timeout, headers=headers)
        if ok:
            results.append(CheckResult("PASS", f"service:{svc_id}", url))
        else:
            lvl = "FAIL" if required else "WARN"
            results.append(CheckResult(lvl, f"service:{svc_id}", f"unreachable: {url}"))

    failures = [r for r in results if r.level == "FAIL"]
    warns = [r for r in results if r.level == "WARN"]

    pass_count = len([r for r in results if r.level == "PASS"])
    sorted_rows = sorted(results, key=lambda r: (level_order(r.level), r.name))
    if args.json:
        payload = {
            "summary": {"pass": pass_count, "warn": len(warns), "fail": len(failures)},
            "checks": [{"level": r.level, "name": r.name, "detail": r.detail} for r in sorted_rows],
        }
        print(json.dumps(payload, indent=2))
    else:
        for row in sorted_rows:
            print(f"{row.level:4} {row.name:<30} {row.detail}")
        print(f"\nSummary: pass={pass_count} warn={len(warns)} fail={len(failures)}")

    if args.strict or args.fail_on_warn:
        return 2 if failures or warns else 0
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
