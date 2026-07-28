"""Static contracts for the disposable foundation replacement prototypes."""

from __future__ import annotations

from pathlib import Path
from subprocess import run


ROOT = Path(__file__).resolve().parents[1]
SPIKE = ROOT / "spikes" / "foundation-replacement"


def test_bootstrap_shell_is_syntactically_valid():
    result = run(
        ["bash", "-n", str(SPIKE / "bootstrap.sh")],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_bootstrap_pins_permissive_candidates_and_excludes_open_webui():
    script = (SPIKE / "bootstrap.sh").read_text()

    assert "a53936d27351e798d320df8f717be3f2272fc49d" in script
    assert "30c047e61b9dc96d9fcb93fbb1d3d5f0f1fec22e" in script
    assert 'grep -qi "MIT License"' in script
    assert "open-webui" not in script.lower()
    assert "openwebui" not in script.lower()


def test_candidate_overlays_route_through_kitty_gateway():
    librechat = (SPIKE / "librechat" / "librechat.yaml").read_text()
    anythingllm = (SPIKE / "anythingllm" / "kitty.env").read_text()

    assert 'baseURL: "http://host.docker.internal:8000/v1"' in librechat
    assert '"kitty-default"' in librechat
    assert "GENERIC_OPEN_AI_BASE_PATH='http://host.docker.internal:8000/v1'" in anythingllm
    assert "GENERIC_OPEN_AI_MODEL_PREF='kitty-default'" in anythingllm
