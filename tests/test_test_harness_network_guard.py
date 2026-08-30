from __future__ import annotations

import os
import socket
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_external_dns_is_blocked_before_network_io() -> None:
    with pytest.raises(RuntimeError, match="external network disabled"):
        socket.getaddrinfo("api.openai.com", 443)


def test_real_loopback_socket_connection_remains_allowed() -> None:
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        client.connect(server.getsockname())
        accepted, _ = server.accept()
        accepted.close()
    finally:
        client.close()
        server.close()


def test_provider_credentials_dotenv_and_paid_lane_are_disabled_by_default() -> None:
    import conftest as harness
    for key in harness._PAID_PROVIDER_KEYS:
        assert key not in os.environ
    assert os.environ["PYTHON_DOTENV_DISABLED"] == "1"
    assert os.environ["KITTY_IMAGE_PAID_ENABLED"] == "0"


def test_canonical_runtime_mutation_is_blocked_in_parent_process() -> None:
    target = ROOT / "data" / ".pytest-must-never-write"
    with pytest.raises(RuntimeError, match="canonical Kitty runtime mutation blocked"):
        target.write_text("unsafe", encoding="utf-8")
    assert not target.exists()


def test_python_subprocess_inherits_runtime_and_network_guard(tmp_path: Path) -> None:
    canonical = ROOT / "data" / ".pytest-child-must-never-write"
    code = f'''\nfrom pathlib import Path\nimport socket\nerrors=[]\ntry:\n    Path({str(canonical)!r}).write_text("unsafe")\nexcept RuntimeError as exc:\n    errors.append("runtime:" + str(exc))\ntry:\n    socket.getaddrinfo("api.openai.com", 443)\nexcept RuntimeError as exc:\n    errors.append("network:" + str(exc))\nprint("\\n".join(errors))\nraise SystemExit(0 if len(errors) == 2 else 9)\n'''
    result = subprocess.run(
        [os.sys.executable, "-c", code],
        cwd=tmp_path,
        env=os.environ.copy(),
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "runtime:canonical Kitty runtime mutation blocked" in result.stdout
    assert "network:external network disabled" in result.stdout
    assert not canonical.exists()


def test_python_subprocess_guard_survives_repo_path_sanitization(tmp_path: Path) -> None:
    probe = tmp_path / "probe.py"
    probe.write_text(
        "import socket\n"
        "print(getattr(socket.socket.connect, '__module__', ''))\n",
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "tests" / "python_startup")

    result = subprocess.run(
        [os.sys.executable, str(probe)],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "kitty_test_guard"


def test_python_subprocess_keeps_parent_dependencies(tmp_path: Path) -> None:
    result = subprocess.run(
        [os.sys.executable, "-c", "import pydantic; print(pydantic.__version__)"],
        cwd=tmp_path,
        env=os.environ.copy(),
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip()


def test_scratch_runtime_root_remains_writable(tmp_path: Path) -> None:
    target = tmp_path / "data" / "ok.txt"
    target.parent.mkdir(parents=True)
    target.write_text("ok", encoding="utf-8")
    assert target.read_text(encoding="utf-8") == "ok"

def test_scratch_relative_data_dir_fd_is_not_mistaken_for_canonical(tmp_path: Path) -> None:
    data = tmp_path / "data"
    data.mkdir()
    target = data / "ok.txt"
    target.write_text("ok", encoding="utf-8")
    base_fd = os.open(tmp_path, os.O_RDONLY)
    try:
        data_fd = os.open("data", os.O_RDONLY, dir_fd=base_fd)
        try:
            os.unlink("ok.txt", dir_fd=data_fd)
        finally:
            os.close(data_fd)
    finally:
        os.close(base_fd)
    assert not target.exists()


def test_canonical_dir_fd_relative_mutation_is_blocked() -> None:
    data_fd = os.open(ROOT / "data", os.O_RDONLY)
    try:
        with pytest.raises(RuntimeError, match="canonical Kitty runtime mutation blocked"):
            os.unlink(".pytest-must-never-unlink", dir_fd=data_fd)
    finally:
        os.close(data_fd)
