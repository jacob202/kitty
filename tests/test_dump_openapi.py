from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHAT = ROOT / "gateway" / "kitty-chat"


def test_dump_openapi_is_deterministic_without_live_gateway(tmp_path: Path) -> None:
    script = ROOT / "scripts" / "dump_openapi.py"
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"

    run1 = subprocess.run(
        [sys.executable, str(script), str(first)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert run1.returncode == 0, run1.stderr
    run2 = subprocess.run(
        [sys.executable, str(script), str(second)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert run2.returncode == 0, run2.stderr
    assert first.read_bytes() == second.read_bytes()
    schema = json.loads(first.read_text(encoding="utf-8"))
    assert "/version" in schema["paths"]


def test_frontend_api_type_generation_is_offline_and_capture_is_generated() -> None:
    package = json.loads((CHAT / "package.json").read_text(encoding="utf-8"))
    command = package["scripts"]["gen:api-types"]
    gateway = (CHAT / "src" / "lib" / "gateway.ts").read_text(encoding="utf-8")

    assert "dump_openapi.py" in command
    assert "http://127.0.0.1" not in command
    assert "components['schemas']['CaptureResponse']" in gateway
