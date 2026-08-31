from __future__ import annotations

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _write_executable(path: Path, body: str) -> None:
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)


def test_builder_launcher_exports_canonical_builder_data_dir(tmp_path: Path) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()

    _write_executable(
        fake_bin / "git",
        "#!/usr/bin/env python3\nprint('/tmp/canonical-kitty/.git')\n",
    )
    _write_executable(
        fake_bin / "python3.12",
        "#!/usr/bin/env python3\nimport os\nprint(os.environ.get('KITTY_BUILDER_DATA_DIR', ''))\n",
    )

    env = dict(os.environ)
    env.pop("KITTY_DATA_ROOT", None)
    env.pop("KITTY_BUILDER_DATA_DIR", None)
    env["PATH"] = f"{fake_bin}:{env['PATH']}"
    # Pin the stub interpreter: on a checkout with venv/bin/python present the
    # launcher would otherwise run the real builder CLI (whose git calls hit
    # the stub and crash), and the test would measure the machine, not the
    # launcher's data-dir resolution.
    env["PYTHON_BIN"] = str(fake_bin / "python3.12")

    result = subprocess.run(
        [str(ROOT / "kitty"), "builder", "initiative", "doctor", "--json"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=20,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == "/tmp/canonical-kitty/data/kittybuilder"

def test_builder_launcher_honors_data_root_before_canonical_checkout(tmp_path: Path) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()

    _write_executable(
        fake_bin / "git",
        "#!/usr/bin/env python3\nprint('/tmp/canonical-kitty/.git')\n",
    )
    _write_executable(
        fake_bin / "python3.12",
        "#!/usr/bin/env python3\nimport os\nprint(os.environ.get('KITTY_BUILDER_DATA_DIR', ''))\n",
    )

    data_root = tmp_path / "isolated-data"
    env = dict(os.environ)
    env["KITTY_DATA_ROOT"] = str(data_root)
    env.pop("KITTY_BUILDER_DATA_DIR", None)
    env["PATH"] = f"{fake_bin}:{env['PATH']}"
    env["PYTHON_BIN"] = str(fake_bin / "python3.12")

    result = subprocess.run(
        [str(ROOT / "kitty"), "builder", "queue", "recover", "--json"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=20,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == str(data_root / "kittybuilder")
