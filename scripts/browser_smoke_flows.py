#!/opt/homebrew/bin/python3.12
"""Deterministic browser-flow smoke checks for Kitty web UI."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from flask import Flask

from src.api.core_routes import core_bp
from src.api.streaming_routes import streaming_bp
from src.api.voice_routes import voice_bp

ARTIFACT_DIR = ROOT / "evals" / "artifacts"


@dataclass(frozen=True)
class FlowCheck:
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


def make_smoke_app() -> Flask:
    app = Flask(
        __name__,
        template_folder=str(ROOT / "src" / "templates"),
        static_folder=str(ROOT / "src" / "static"),
    )
    app.config["TESTING"] = True
    app.register_blueprint(streaming_bp)
    app.register_blueprint(core_bp)
    app.register_blueprint(voice_bp)
    return app


def check_voice_transition_contract(html: str) -> tuple[bool, list[str]]:
    required_tokens = [
        "setVoiceState('recording'",
        "setVoiceState('transcribing'",
        "setVoiceState('unsupported'",
        "toggleVoiceInput",
        "if (voiceState === 'recording')",
        "await sendMsg();",
    ]
    missing = [token for token in required_tokens if token not in html]
    return (len(missing) == 0, missing)


def run_browser_smoke(app: Flask) -> tuple[list[FlowCheck], float]:
    checks: list[FlowCheck] = []

    with app.test_client() as client:
        page = client.get("/")
        html = page.get_data(as_text=True)

        checks.append(
            FlowCheck(
                name="page_load",
                passed=(page.status_code == 200 and 'id="inp"' in html and 'id="voice-toggle"' in html),
                status=page.status_code,
                reason="" if page.status_code == 200 else f"status={page.status_code}",
                details={"has_chat_input": 'id="inp"' in html, "has_voice_toggle": 'id="voice-toggle"' in html},
            )
        )

        chat = client.post("/api/chat", json={"message": "browser smoke ping", "domain": "chat"})
        chat_json = chat.get_json(silent=True) or {}
        chat_text = str(chat_json.get("response") or "").strip()
        checks.append(
            FlowCheck(
                name="text_chat_roundtrip",
                passed=(chat.status_code == 200 and bool(chat_json.get("ok")) and bool(chat_text)),
                status=chat.status_code,
                reason="" if chat.status_code == 200 else f"status={chat.status_code}",
                details={"response_preview": chat_text[:120]},
            )
        )

        voice_ok, missing = check_voice_transition_contract(html)
        checks.append(
            FlowCheck(
                name="voice_state_transitions",
                passed=voice_ok,
                status=200,
                reason="" if voice_ok else f"missing tokens: {', '.join(missing)}",
                details={"missing_tokens": missing},
            )
        )

        voice = client.post("/api/transcribe", data={}, content_type="multipart/form-data")
        voice_json = voice.get_json(silent=True) or {}
        voice_error = str(voice_json.get("error") or "")
        checks.append(
            FlowCheck(
                name="voice_endpoint_guard",
                passed=(voice.status_code == 400 and "audio file is required" in voice_error.lower()),
                status=voice.status_code,
                reason="" if voice.status_code == 400 else f"status={voice.status_code}",
                details={"error": voice_error},
            )
        )

    passed = sum(1 for c in checks if c.passed)
    rate = passed / len(checks) if checks else 0.0
    return checks, rate


def write_artifact(
    checks: list[FlowCheck],
    rate: float,
    *,
    output_dir: Path = ARTIFACT_DIR,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_id = f"browser_flow_{ts}"
    artifact = {
        "run_id": run_id,
        "suite": "browser_flow",
        "started_at": ts,
        "scores": {
            "browser_flow": {
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
    parser = argparse.ArgumentParser(description="Run deterministic browser-flow smoke checks.")
    parser.add_argument("--no-artifact", action="store_true", help="Do not write eval artifact")
    parser.add_argument("--artifact-dir", default=str(ARTIFACT_DIR), help="Artifact output directory")
    args = parser.parse_args(argv)

    checks, rate = run_browser_smoke(make_smoke_app())
    print(f"Browser flow smoke: {sum(1 for c in checks if c.passed)}/{len(checks)} ({rate:.0%})")
    for check in checks:
        icon = "PASS" if check.passed else "FAIL"
        msg = check.reason if check.reason else "ok"
        print(f"- {icon} {check.name}: {msg}")

    if not args.no_artifact:
        artifact = write_artifact(checks, rate, output_dir=Path(args.artifact_dir))
        print(f"Artifact: {artifact}")

    return 0 if all(c.passed for c in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
