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
            'export KITTY_ENV="${KITTY_ENV:-prod}"',
        ],
        "gateway/start_litellm.sh": [
            'source "${ROOT_DIR}/gateway/lib/load_env_safe.sh"',
            'LITELLM_CONFIG="${LITELLM_CONFIG:-gateway/litellm_config.yaml}"',
            'LITELLM_REQUIREMENTS_FILE="${LITELLM_REQUIREMENTS_FILE:-gateway/requirements.litellm.txt}"',
        ],
        "gateway/start_openwebui.sh": [
            'source "gateway/lib/load_env_safe.sh"',
        ],
        "gateway/start_tool_servers.sh": [
            'source "${ROOT_DIR}/gateway/lib/load_env_safe.sh"',
        ],
        "gateway/status_all.sh": [
            'source "${ROOT_DIR}/gateway/lib/load_env_safe.sh"',
        ],
        "gateway/doctor.sh": [
            'exec "${PYTHON_BIN}" "${ROOT_DIR}/gateway/doctor.py" "$@"',
        ],
        "gateway/run_doctor_check.sh": [
            'json_out="$(bash gateway/doctor.sh --json 2>/dev/null || true)"',
        ],
    }

    for rel_path, snippets in expected_snippets.items():
        contents = _read_text(rel_path)
        for snippet in snippets:
            assert snippet in contents, f"{rel_path} is missing {snippet!r}"


def test_start_all_and_runtime_manifest_point_at_live_gateway_scripts() -> None:
    start_all = _read_text("gateway/start_all.sh")
    for snippet in (
        'source "${ROOT_DIR}/gateway/lib/load_env_safe.sh"',
        'source "${ROOT_DIR}/gateway/lib/openwebui_probe.sh"',
        "bash gateway/start_litellm.sh",
        "bash gateway/start_gateway.sh",
        "bash gateway/start_openwebui.sh",
        "bash gateway/start_jupyter_exec.sh",
        "bash gateway/start_tool_servers.sh",
        "bash gateway/doctor.sh",
    ):
        assert snippet in start_all

    manifest = json.loads(_read_text("gateway/runtime_manifest.json"))
    assert manifest["required_files"] == [
        "kitty_gateway/openwebui.env",
        "gateway/start_all.sh",
        "gateway/sync_openwebui_integrations.sh",
        "gateway/import_openwebui_functions.sh",
        "gateway/openwebui_filters/kitty_context_injector.py",
    ]

