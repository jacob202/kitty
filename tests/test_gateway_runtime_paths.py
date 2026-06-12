from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read_text(rel_path: str) -> str:
    return (ROOT / rel_path).read_text(encoding="utf-8")


def test_gateway_launcher_scripts_use_live_gateway_paths() -> None:
    expected_snippets = {
        "gateway/start_gateway.sh": [
            'source "${ROOT_DIR}/gateway/lib/load_env_safe.sh"',
            'GATEWAY_PORT="${GATEWAY_PORT:-5001}"',
        ],
        "gateway/start_litellm.sh": [
            'source "${ROOT_DIR}/gateway/lib/load_env_safe.sh"',
            'LITELLM_CONFIG="${LITELLM_CONFIG:-gateway/litellm_config.yaml}"',
            'LITELLM_REQUIREMENTS_FILE="${LITELLM_REQUIREMENTS_FILE:-gateway/requirements.litellm.txt}"',
        ],
        "gateway/status_all.sh": [
            'source "${ROOT_DIR}/gateway/lib/load_env_safe.sh"',
        ],
    }

    for rel_path, snippets in expected_snippets.items():
        contents = _read_text(rel_path)
        for snippet in snippets:
            assert snippet in contents, f"{rel_path} is missing {snippet!r}"


def test_launcher_scripts_do_not_hardcode_user_paths() -> None:
    for rel_path in (
        "gateway/start_all.sh",
        "gateway/start_gateway.sh",
        "gateway/start_litellm.sh",
        "gateway/status_all.sh",
        "gateway/stop_all.sh",
    ):
        assert "/Users/" not in _read_text(rel_path), f"{rel_path} hardcodes a user path"


def test_start_all_and_runtime_manifest_point_at_live_gateway_scripts() -> None:
    start_all = _read_text("gateway/start_all.sh")
    for snippet in (
        'source "${ROOT_DIR}/gateway/lib/load_env_safe.sh"',
        "bash gateway/start_litellm.sh",
        "bash gateway/start_gateway.sh",
    ):
        assert snippet in start_all

    manifest = json.loads(_read_text("gateway/runtime_manifest.json"))
    required = {f for f in manifest["required_files"]}
    for rel_path in required:
        assert (ROOT / rel_path).exists(), f"runtime manifest cites missing file {rel_path}"
