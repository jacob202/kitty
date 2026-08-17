from __future__ import annotations

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_data_root_can_be_overridden_for_isolated_runtimes(tmp_path: Path) -> None:
    data_root = tmp_path / "isolated-data"
    env = {**os.environ, "KITTY_DATA_ROOT": str(data_root)}
    env.pop("KITTY_BUILDER_DATA_DIR", None)

    result = subprocess.run(
        [
            os.sys.executable,
            "-c",
            (
                "from gateway import paths; "
                "print(paths.DATA_DIR); "
                "print(paths.KITTY_DATA_DIR); "
                "print(paths.KITTYBUILDER_DIR)"
            ),
        ],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )

    assert result.stdout.splitlines() == [
        str(data_root),
        str(data_root / "kitty"),
        str(data_root / "kittybuilder"),
    ]


def test_pytest_session_uses_a_scratch_data_root() -> None:
    from gateway import paths

    assert paths.DATA_DIR != ROOT / "data"
    assert os.environ.get("KITTY_DATA_ROOT") == str(paths.DATA_DIR)
    assert os.environ.get("KITTY_BUILDER_DATA_DIR") == str(paths.KITTYBUILDER_DIR)
