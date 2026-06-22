from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read_text(rel_path: str) -> str:
    return (ROOT / rel_path).read_text(encoding="utf-8")


# Matches an absolute path assigned directly to ROOT_DIR: ROOT_DIR=/...,
# ROOT_DIR="/...", or ROOT_DIR='/...'. The portable form is
# ROOT_DIR="$(cd ... && pwd)", where the char after the quote is "$", not "/",
# so this only fires on a hardcoded machine path — on any OS, not just macOS.
_HARDCODED_ROOT_DIR = re.compile(r"""ROOT_DIR=['"]?/""")


def test_no_shell_script_hardcodes_an_absolute_repo_path() -> None:
    """A2: launchers must resolve their own location, never hardcode a machine path.

    The repo has repeatedly regressed to ROOT_DIR="/Users/jacobbrizinski/..."
    which breaks any other clone. Shell scripts must derive ROOT_DIR from
    BASH_SOURCE instead, so a fresh clone works without editing. The pattern is
    anchored on ROOT_DIR= (rather than a substring like "/Users/") so it also
    catches a "/home/..." or "/opt/..." regression without false-positiving on
    legitimate absolute paths elsewhere in the scripts (e.g. PATH entries).
    """
    offenders = []
    for sh in sorted(ROOT.glob("gateway/*.sh")):
        text = sh.read_text(encoding="utf-8")
        if _HARDCODED_ROOT_DIR.search(text):
            offenders.append(sh.name)
    assert not offenders, f"hardcoded absolute ROOT_DIR in: {offenders}"


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
        "bash gateway/start_litellm.sh",
        "bash gateway/start_gateway.sh",
        "bash gateway/start_jupyter_exec.sh",
        "bash gateway/start_tool_servers.sh",
        "bash gateway/doctor.sh",
    ):
        assert snippet in start_all

    # Open WebUI has been removed from the stack — start_all must not reference it.
    assert "openwebui" not in start_all.lower()

    manifest = json.loads(_read_text("gateway/runtime_manifest.json"))
    assert manifest["required_files"] == [
        "gateway/start_all.sh",
        "gateway/start_gateway.sh",
        "gateway/start_litellm.sh",
    ]
    service_ids = {svc["id"] for svc in manifest["services"]}
    assert "openwebui" not in service_ids
    assert "openwebui" not in manifest

