#!/opt/homebrew/bin/python3.12
"""Daily flow scorecard for Kitty + KittyBuilder reliability tracking.

Checks the primary customer flow endpoints and writes an append-only artifact:
evals/artifacts/daily_flow_<timestamp>.json
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib import error, request


ARTIFACT_DIR = Path(__file__).resolve().parent.parent / "evals" / "artifacts"


@dataclass(frozen=True)
class CheckResult:
    name: str
    passed: bool
    status: int | None
    reason: str = ""
    details: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "passed": self.passed,
            "status": self.status,
            "reason": self.reason,
            "details": self.details or {},
        }


def _request_json(url: str, method: str = "GET", payload: dict[str, Any] | None = None) -> tuple[int | None, dict[str, Any], str]:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"} if payload is not None else {}
    req = request.Request(url, data=body, headers=headers, method=method)
    try:
        with request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            try:
                parsed = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                parsed = {}
            return resp.status, parsed, raw
    except error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            parsed = {}
        return exc.code, parsed, raw
    except Exception as exc:  # noqa: BLE001 - scorecard should never crash hard
        return None, {}, str(exc)


def _request_client_json(client: Any, path: str, method: str = "GET", payload: dict[str, Any] | None = None) -> tuple[int | None, dict[str, Any], str]:
    kwargs: dict[str, Any] = {"method": method}
    if payload is not None:
        kwargs["json"] = payload
    resp = client.open(path, **kwargs)
    raw = resp.get_data(as_text=True)
    data = resp.get_json(silent=True) or {}
    if not isinstance(data, dict):
        data = {}
    return resp.status_code, data, raw


def _run_scorecard(
    fetch: Any,
    *,
    smoke_baseline: float = 0.95,
) -> tuple[list[CheckResult], float]:
    checks: list[CheckResult] = []

    status, data, raw = fetch("/api/brief")
    brief_data = data.get("data") if isinstance(data.get("data"), dict) else {}
    next_action = data.get("next_action") or brief_data.get("next_action") or data.get("brief")
    checks.append(
        CheckResult(
            name="brief_available",
            passed=(status == 200 and isinstance(data, dict) and bool(next_action)),
            status=status,
            reason="" if status == 200 else f"status={status} body={raw[:240]}",
            details={"next_action": next_action},
        )
    )

    status, data, raw = fetch(
        "/api/chat",
        method="POST",
        payload={"message": "daily flow scorecard ping", "domain": "chat"},
    )
    chat_text = str(data.get("response") or data.get("text") or "").strip()
    checks.append(
        CheckResult(
            name="chat_responds",
            passed=(status == 200 and bool(chat_text)),
            status=status,
            reason="" if status == 200 else f"status={status} body={raw[:240]}",
            details={"response_preview": chat_text[:160]},
        )
    )

    status, data, raw = fetch(
        "/api/command",
        method="POST",
        payload={"command": "/help"},
    )
    help_text = str(data.get("response") or "").strip()
    checks.append(
        CheckResult(
            name="command_help_surface",
            passed=(status == 200 and "Commands" in help_text),
            status=status,
            reason="" if status == 200 else f"status={status} body={raw[:240]}",
            details={"response_preview": help_text[:160]},
        )
    )

    status, data, raw = fetch(
        "/api/command",
        method="POST",
        payload={"command": "/stuck"},
    )
    next_action = (data.get("action") or {}).get("next_action")
    checks.append(
        CheckResult(
            name="command_stuck_action",
            passed=(status == 200 and bool(next_action)),
            status=status,
            reason="" if status == 200 else f"status={status} body={raw[:240]}",
            details={"next_action": next_action},
        )
    )

    status, data, raw = fetch(
        "/api/eval/run",
        method="POST",
        payload={"suite": "smoke"},
    )
    smoke_rate = float(((data.get("score") or {}).get("rate") or 0.0))
    checks.append(
        CheckResult(
            name="smoke_eval_baseline",
            passed=(status == 200 and smoke_rate >= smoke_baseline),
            status=status,
            reason="" if status == 200 else f"status={status} body={raw[:240]}",
            details={"smoke_rate": smoke_rate, "baseline": smoke_baseline},
        )
    )

    passed = sum(1 for c in checks if c.passed)
    rate = passed / len(checks) if checks else 0.0
    return checks, rate


def run_scorecard(base_url: str, smoke_baseline: float = 0.95) -> tuple[list[CheckResult], float]:
    root = base_url.rstrip("/")

    def fetch(path: str, method: str = "GET", payload: dict[str, Any] | None = None) -> tuple[int | None, dict[str, Any], str]:
        return _request_json(f"{root}{path}", method=method, payload=payload)

    return _run_scorecard(fetch, smoke_baseline=smoke_baseline)


def run_scorecard_client(client: Any, smoke_baseline: float = 0.95) -> tuple[list[CheckResult], float]:
    def fetch(path: str, method: str = "GET", payload: dict[str, Any] | None = None) -> tuple[int | None, dict[str, Any], str]:
        return _request_client_json(client, path, method=method, payload=payload)

    return _run_scorecard(fetch, smoke_baseline=smoke_baseline)


def write_artifact(
    checks: list[CheckResult],
    rate: float,
    *,
    base_url: str,
    output_dir: Path = ARTIFACT_DIR,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_id = f"daily_flow_{ts}"
    artifact = {
        "run_id": run_id,
        "suite": "daily_flow",
        "base_url": base_url,
        "started_at": ts,
        "scores": {
            "daily_flow": {
                "passed": sum(1 for c in checks if c.passed),
                "total": len(checks),
                "rate": rate,
            }
        },
        "checks": [c.to_dict() for c in checks],
    }
    path = output_dir / f"{run_id}.json"
    path.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate a daily flow reliability scorecard.")
    parser.add_argument("--base-url", default="http://localhost:5001", help="Kitty base URL")
    parser.add_argument("--smoke-baseline", type=float, default=0.95, help="Required /api/eval/run smoke score")
    args = parser.parse_args(argv)

    checks, rate = run_scorecard(args.base_url, smoke_baseline=args.smoke_baseline)
    artifact_path = write_artifact(checks, rate, base_url=args.base_url)

    print(f"Scorecard: {sum(1 for c in checks if c.passed)}/{len(checks)} ({rate:.0%})")
    print(f"Artifact: {artifact_path}")
    for c in checks:
        icon = "PASS" if c.passed else "FAIL"
        msg = c.reason if c.reason else "ok"
        print(f"- {icon} {c.name}: {msg}")

    return 0 if all(c.passed for c in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
