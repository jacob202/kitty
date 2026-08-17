"""Trust gate provenance: prove pytest is testing the intended checkout/state."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys


def _git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


def test_pytest_gate_proves_checkout_head_interpreter_and_data_namespace() -> None:
    root = Path(__file__).resolve().parents[1]
    expected_checkout = Path(os.environ.get("KITTY_EXPECTED_TEST_CHECKOUT", root)).resolve()
    assert root == expected_checkout
    assert Path(_git(root, "rev-parse", "--show-toplevel")).resolve() == root

    actual_head = _git(root, "rev-parse", "HEAD")
    expected_head = os.environ.get("KITTY_EXPECTED_TEST_HEAD", actual_head)
    assert actual_head == expected_head

    assert sys.version_info[:2] == (3, 12), sys.executable

    data_root_raw = os.environ.get("KITTY_DATA_ROOT")
    assert data_root_raw, "pytest harness did not establish KITTY_DATA_ROOT"
    data_root = Path(data_root_raw).resolve()
    assert data_root != (root / "data").resolve()
    assert root not in data_root.parents, f"test data root leaked inside checkout: {data_root}"
