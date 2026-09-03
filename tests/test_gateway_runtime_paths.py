from __future__ import annotations

import os
import re
import subprocess
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
    }

    for rel_path, snippets in expected_snippets.items():
        contents = _read_text(rel_path)
        for snippet in snippets:
            assert snippet in contents, f"{rel_path} is missing {snippet!r}"


def test_litellm_launcher_avoids_repo_package_shadowing(tmp_path: Path) -> None:
    fake_venv = tmp_path / "venv-litellm"
    fake_bin = fake_venv / "bin"
    fake_bin.mkdir(parents=True)
    capture_path = tmp_path / "litellm-launch.txt"

    (fake_bin / "activate").write_text(
        f'export PATH="{fake_bin}:$PATH"\n',
        encoding="utf-8",
    )
    for name, body in {
        "python": "#!/bin/bash\nexit 0\n",
        "litellm": (
            "#!/bin/bash\n"
            'printf "%s\\n" "$PWD" >"$LITELLM_CAPTURE"\n'
            'printf "PYTHONPATH=%s\\n" "${PYTHONPATH-}" >>"$LITELLM_CAPTURE"\n'
            'printf "%s\\n" "$@" >>"$LITELLM_CAPTURE"\n'
        ),
    }.items():
        executable = fake_bin / name
        executable.write_text(body, encoding="utf-8")
        executable.chmod(0o755)

    env = {
        **os.environ,
        "LITELLM_CAPTURE": str(capture_path),
        "LITELLM_VENV": str(fake_venv),
        "PYTHONPATH": str(ROOT),
    }
    result = subprocess.run(
        ["bash", str(ROOT / "gateway/start_litellm.sh")],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    launch = capture_path.read_text(encoding="utf-8").splitlines()
    assert launch[0] == str(fake_venv.resolve())
    assert launch[1] == "PYTHONPATH="
    config_index = launch.index("--config")
    assert launch[config_index + 1] == str(
        (ROOT / "gateway/litellm_config.yaml").resolve()
    )



def test_litellm_launcher_keeps_repo_owned_supervisor_process(tmp_path: Path) -> None:
    """The tracked launcher PID must keep a repo cwd while LiteLLM stays isolated."""
    import shutil
    import signal
    import time

    fake_venv = tmp_path / "venv-litellm"
    fake_bin = fake_venv / "bin"
    fake_bin.mkdir(parents=True)
    ready_path = tmp_path / "litellm-ready"

    (fake_bin / "activate").write_text(
        f'export PATH="{fake_bin}:$PATH"\n',
        encoding="utf-8",
    )
    python = fake_bin / "python"
    python.write_text("#!/bin/bash\nexit 0\n", encoding="utf-8")
    python.chmod(0o755)
    litellm = fake_bin / "litellm"
    litellm.write_text(
        "#!/bin/bash\n"
        'printf "ready\\n" >"$LITELLM_READY"\n'
        "trap 'exit 0' TERM INT\n"
        "while :; do sleep 1; done\n",
        encoding="utf-8",
    )
    litellm.chmod(0o755)

    env = {
        **os.environ,
        "LITELLM_READY": str(ready_path),
        "LITELLM_VENV": str(fake_venv),
    }
    proc = subprocess.Popen(
        ["bash", str(ROOT / "gateway/start_litellm.sh")],
        cwd=ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    try:
        for _ in range(50):
            if ready_path.exists():
                break
            time.sleep(0.1)
        assert ready_path.exists(), proc.stderr.read() if proc.poll() is not None else ""

        proc_link = Path(f"/proc/{proc.pid}/cwd")
        if proc_link.exists():
            supervisor_cwd = proc_link.resolve()
        else:
            lsof = shutil.which("lsof")
            assert lsof is not None, "need /proc or lsof to inspect process cwd"
            result = subprocess.run(
                [lsof, "-a", "-p", str(proc.pid), "-d", "cwd", "-Fn"],
                capture_output=True,
                text=True,
                check=True,
            )
            cwd_line = next(line for line in result.stdout.splitlines() if line.startswith("n"))
            supervisor_cwd = Path(cwd_line[1:]).resolve()

        assert supervisor_cwd == ROOT.resolve()
    finally:
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.wait(timeout=5)


def test_kitty_launcher_points_at_live_gateway_scripts() -> None:
    launcher = _read_text("kitty")
    assert 'bash "$KITTY_ROOT/gateway/start_litellm.sh"' in launcher
    assert 'bash "$KITTY_ROOT/gateway/start_gateway.sh"' in launcher
    assert "start_tool_servers.sh" not in launcher
    assert "start_all.sh" not in launcher


def test_litellm_dependency_contract_is_self_consistent_and_proxy_ready() -> None:
    """Tracked install instructions and launcher preflight must enforce one contract."""
    from packaging.requirements import Requirement

    requirements = [
        Requirement(line.strip())
        for line in _read_text("gateway/requirements.litellm.txt").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    by_name = {requirement.name.lower(): requirement for requirement in requirements}

    assert "proxy" in by_name["litellm"].extras
    openai_specifiers = list(by_name["openai"].specifier)
    assert len(openai_specifiers) == 1
    assert openai_specifiers[0].operator == "=="

    launcher = _read_text("gateway/start_litellm.sh")
    assert 'md.version("openai") == "2.24.0"' not in launcher
    assert "from packaging.requirements import Requirement" in launcher
    assert "import websockets" in launcher
    assert "openai_requirement.specifier" in launcher
