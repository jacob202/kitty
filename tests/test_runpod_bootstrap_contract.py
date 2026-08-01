"""Runtime contract tests for the immutable RunPod worker bootstrap."""

from __future__ import annotations

import json
import os
import signal
import socket
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ENTRYPOINT = ROOT / "workers" / "comfy_worker" / "entrypoint-kitty.sh"
BOOTSTRAP = ROOT / "workers" / "comfy_worker" / "bootstrap.sh"
DOCKERFILE = ROOT / "workers" / "comfy_worker" / "Dockerfile"


def _unused_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _health(port: int) -> tuple[int, dict[str, object]] | None:
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/health", timeout=1
        ) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))
    except OSError:
        return None


@pytest.mark.skipif(os.name != "posix", reason="worker image is Linux-only")
def test_entrypoint_keeps_structured_health_after_bootstrap_failure(tmp_path: Path):
    port = _unused_port()
    env = os.environ.copy()
    env.update(
        {
            "KITTY_WORKER_PORT": str(port),
            "KITTY_STATE_FILE": str(tmp_path / "state.json"),
            "KITTY_STAGE_PIDFILE": str(tmp_path / "stage.pid"),
            "KITTY_STAGE_SERVER_PY": str(tmp_path / "stage-server.py"),
        }
    )
    process = subprocess.Popen(
        ["bash", str(ENTRYPOINT), "bash", "-c", "exit 7"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        start_new_session=True,
    )
    try:
        deadline = time.monotonic() + 10
        result = None
        while time.monotonic() < deadline:
            result = _health(port)
            if result is not None and result[1].get("status") == "failed":
                break
            time.sleep(0.1)

        assert result is not None
        status, body = result
        assert status == 503
        assert body["status"] == "failed"
        assert body["stage"] == "bootstrap-starting"
        assert body["exit_code"] == 7
        assert "bootstrap exited non-zero" in str(body["error"])
        assert process.poll() is None
    finally:
        if process.poll() is None:
            process.send_signal(signal.SIGTERM)
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=5)

    assert _health(port) is None


def test_worker_image_uses_runpod_baked_comfyui_root():
    dockerfile = DOCKERFILE.read_text(encoding="utf-8")
    bootstrap = BOOTSTRAP.read_text(encoding="utf-8")

    assert "COMFYUI_ROOT=/opt/comfyui-baked" in dockerfile
    assert 'COMFYUI_ROOT="${COMFYUI_ROOT:-/opt/comfyui-baked}"' in bootstrap
    assert '"/opt/comfyui-baked"' in bootstrap


def test_checkpoint_hashing_is_streamed_not_read_whole():
    bootstrap = BOOTSTRAP.read_text(encoding="utf-8")

    assert "handle.read(1024 * 1024)" in bootstrap
    assert "open(sys.argv[1],'rb').read()" not in bootstrap
