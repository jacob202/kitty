#!/usr/bin/env python3
"""Kitty gateway preflight/health doctor."""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any


ROOT_DIR = pathlib.Path("/Users/jacobbrizinski/Projects/kitty")
ENV_FILE = ROOT_DIR / "kitty_gateway" / "openwebui.env"
MANIFEST_FILE = ROOT_DIR / "kitty_gateway" / "runtime_manifest.json"


@dataclass
class CheckResult:
    level: str  # PASS|WARN|FAIL
    name: str
    detail: str


def parse_env(path: pathlib.Path) -> dict[str, str]:
    data: dict[str, str] = {}
    if not path.exists():
        return data
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if (value.startswith('"') and value.endswith('"')) or (
            value.startswith("'") and value.endswith("'")
        ):
            value = value[1:-1]
        data[key] = os.path.expandvars(value)
    return data


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


def parse_json_env(key: str, value: str, results: list[CheckResult]) -> list[dict[str, Any]]:
    if not value:
        results.append(CheckResult("FAIL", key, "missing"))
        return []
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        results.append(CheckResult("FAIL", key, f"invalid JSON: {exc}"))
        return []
    if not isinstance(parsed, list):
        results.append(CheckResult("FAIL", key, "must be a JSON list"))
        return []
    results.append(CheckResult("PASS", key, f"{len(parsed)} entries"))
    return [item for item in parsed if isinstance(item, dict)]


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
    # Keep file parsing only as fallback when doctor.py is run directly.
    for key, value in parse_env(ENV_FILE).items():
        env.setdefault(key, value)

    if not ENV_FILE.exists():
        results.append(CheckResult("FAIL", "openwebui.env", f"missing: {ENV_FILE}"))
    else:
        results.append(CheckResult("PASS", "openwebui.env", str(ENV_FILE)))

    for rel in manifest.get("required_files", []):
        path = ROOT_DIR / rel
        if path.exists():
            results.append(CheckResult("PASS", f"file:{rel}", "present"))
        else:
            results.append(CheckResult("FAIL", f"file:{rel}", "missing"))

    data_dir = pathlib.Path(env.get("OPENWEBUI_DATA_DIR", str(pathlib.Path.home() / "kitty-services/open-webui-data")))
    db_path = data_dir / "webui.db"
    if db_path.exists():
        results.append(CheckResult("PASS", "openwebui.db", str(db_path)))
    else:
        results.append(CheckResult("WARN", "openwebui.db", f"not found at {db_path}"))

    _ = parse_json_env("TOOL_SERVER_CONNECTIONS", env.get("TOOL_SERVER_CONNECTIONS", ""), results)
    _ = parse_json_env("TERMINAL_SERVER_CONNECTIONS", env.get("TERMINAL_SERVER_CONNECTIONS", ""), results)

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

    webui_url = env.get("WEBUI_URL", "http://127.0.0.1:3000").rstrip("/")
    email = env.get("WEBUI_ADMIN_EMAIL", "")
    password = env.get("WEBUI_ADMIN_PASSWORD", "")
    token = ""

    try:
        code, payload = http_json(
            f"{webui_url}/api/v1/auths/signin",
            method="POST",
            body={"email": email, "password": password},
            timeout=6.0,
        )
        if code >= 400 or not isinstance(payload, dict):
            results.append(CheckResult("FAIL", "openwebui_auth", f"signin failed ({code})"))
        else:
            token = str(payload.get("token", "") or "")
            if token:
                results.append(CheckResult("PASS", "openwebui_auth", "admin auth ok"))
            else:
                results.append(CheckResult("FAIL", "openwebui_auth", "token missing in signin response"))
    except urllib.error.URLError as exc:
        results.append(CheckResult("FAIL", "openwebui_auth", f"signin error: {exc.reason}"))
    except Exception as exc:
        results.append(CheckResult("FAIL", "openwebui_auth", f"signin error: {exc}"))

    if token:
        headers = {"Authorization": f"Bearer {token}"}
        try:
            _, tool_cfg = http_json(f"{webui_url}/api/v1/configs/tool_servers", headers=headers, timeout=6.0)
            _, term_cfg = http_json(f"{webui_url}/api/v1/configs/terminal_servers", headers=headers, timeout=6.0)
            _, functions = http_json(f"{webui_url}/api/v1/functions/", headers=headers, timeout=6.0)
        except Exception as exc:
            results.append(CheckResult("FAIL", "openwebui_api", f"read config/function APIs failed: {exc}"))
            tool_cfg = {}
            term_cfg = {}
            functions = []

        tool_servers = []
        if isinstance(tool_cfg, dict):
            tool_servers = tool_cfg.get("TOOL_SERVER_CONNECTIONS", []) or []
        terminal_servers = []
        if isinstance(term_cfg, dict):
            terminal_servers = term_cfg.get("TERMINAL_SERVER_CONNECTIONS", []) or []
        fn_count = len(functions) if isinstance(functions, list) else 0

        manifest_openwebui = manifest.get("openwebui", {})
        req_tool_ids = set(manifest_openwebui.get("required_tool_server_ids", []))
        req_term_ids = set(manifest_openwebui.get("required_terminal_server_ids", []))
        min_functions = int(manifest_openwebui.get("min_functions", 0))

        got_tool_ids = {str(item.get("id", "")) for item in tool_servers if isinstance(item, dict)}
        got_term_ids = {str(item.get("id", "")) for item in terminal_servers if isinstance(item, dict)}

        missing_tools = sorted(req_tool_ids - got_tool_ids)
        missing_terms = sorted(req_term_ids - got_term_ids)

        if missing_tools:
            results.append(CheckResult("FAIL", "openwebui_tool_servers", f"missing: {', '.join(missing_tools)}"))
        else:
            results.append(CheckResult("PASS", "openwebui_tool_servers", f"{len(got_tool_ids)} configured"))
        if missing_terms:
            results.append(CheckResult("FAIL", "openwebui_terminal_servers", f"missing: {', '.join(missing_terms)}"))
        else:
            results.append(CheckResult("PASS", "openwebui_terminal_servers", f"{len(got_term_ids)} configured"))

        if fn_count < min_functions:
            results.append(CheckResult("WARN", "openwebui_functions", f"{fn_count} loaded, expected >= {min_functions}"))
        else:
            results.append(CheckResult("PASS", "openwebui_functions", f"{fn_count} loaded"))

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
