from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "dump_openapi.py"
PACKAGE = ROOT / "gateway" / "kitty-chat" / "package.json"


def test_dump_openapi_generates_current_schema_without_live_gateway(tmp_path: Path) -> None:
    output = tmp_path / "openapi.json"
    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(output)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    schema = json.loads(output.read_text(encoding="utf-8"))
    assert schema["openapi"].startswith("3.")
    assert "/version" in schema["paths"]
    assert schema.get("components", {}).get("schemas")


def test_frontend_type_generation_uses_offline_schema_dump() -> None:
    package = json.loads(PACKAGE.read_text(encoding="utf-8"))
    command = package["scripts"]["gen:api-types"]
    assert "dump_openapi.py" in command
    assert "127.0.0.1:8000" not in command
    assert "src/lib/gen/openapi.json" in command
