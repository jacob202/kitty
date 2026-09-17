"""The pre-push gate lock serializes heavy gates across worktrees.

Concurrent full suites on one machine thrash: several worktrees' pre-push gates
at once turned a six-minute suite into fifteen-plus minutes of swap-bound noise
(observed 2026-09-17). `scripts/hooks/gate_lock.py` wraps the heavy gates in one
exclusive lock; these tests pin its contract without needing a full gate run.
"""

from __future__ import annotations

import fcntl
import os
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
GATE_LOCK = REPO_ROOT / "scripts" / "hooks" / "gate_lock.py"


def _run(args: list[str], *, lock_path: Path, timeout: str = "30") -> subprocess.CompletedProcess[str]:
    env = {
        **os.environ,
        "KITTY_GATE_LOCK_PATH": str(lock_path),
        "KITTY_GATE_LOCK_TIMEOUT": timeout,
        "KITTY_GATE_LOCK_HELD": "",
    }
    return subprocess.run(
        [sys.executable, str(GATE_LOCK), "--", *args],
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )


def test_runs_the_command_and_passes_through_its_exit_status(tmp_path: Path) -> None:
    ok = _run([sys.executable, "-c", "print('ran')"], lock_path=tmp_path / "gate.lock")
    assert ok.returncode == 0
    assert "ran" in ok.stdout

    bad = _run([sys.executable, "-c", "raise SystemExit(3)"], lock_path=tmp_path / "gate.lock")
    assert bad.returncode == 3


def test_waits_for_a_held_lock_then_acquires_it(tmp_path: Path) -> None:
    lock_file = tmp_path / "gate.lock"
    holder = subprocess.Popen(
        [
            sys.executable,
            "-c",
            (
                "import fcntl, sys, time\n"
                "handle = open(sys.argv[1], 'a+')\n"
                "fcntl.flock(handle, fcntl.LOCK_EX)\n"
                "time.sleep(2.0)\n"
                "fcntl.flock(handle, fcntl.LOCK_UN)\n"
            ),
            str(lock_file),
        ],
    )
    try:
        time.sleep(0.2)  # let the holder take the lock first
        result = _run([sys.executable, "-c", "print('ran')"], lock_path=lock_file, timeout="15")
    finally:
        holder.wait(timeout=30)

    assert result.returncode == 0
    assert "ran" in result.stdout
    assert "waiting" in result.stderr
    assert "acquired after" in result.stderr


def test_proceeds_without_the_lock_after_the_timeout(tmp_path: Path) -> None:
    lock_file = tmp_path / "gate.lock"
    with lock_file.open("a+") as holder:
        fcntl.flock(holder, fcntl.LOCK_EX)
        holder.seek(0)
        holder.truncate()
        holder.write(f"{os.getpid()}\n")
        holder.flush()
        result = _run([sys.executable, "-c", "print('ran anyway')"], lock_path=lock_file, timeout="1")

    assert result.returncode == 0
    assert "ran anyway" in result.stdout
    assert "without it" in result.stderr


def test_degrades_loudly_when_the_lock_path_is_a_symlink(tmp_path: Path) -> None:
    target = tmp_path / "target.txt"
    target.write_text("untouched")
    lock_link = tmp_path / "gate.lock"
    lock_link.symlink_to(target)

    result = _run([sys.executable, "-c", "print('ran')"], lock_path=lock_link)

    assert result.returncode == 0
    assert "ran" in result.stdout
    assert "unavailable" in result.stderr
    assert target.read_text() == "untouched"


def test_degrades_loudly_when_the_lock_path_is_a_directory(tmp_path: Path) -> None:
    lock_dir = tmp_path / "gate.lock"
    lock_dir.mkdir()

    result = _run([sys.executable, "-c", "print('ran')"], lock_path=lock_dir)

    assert result.returncode == 0
    assert "ran" in result.stdout
    assert "unavailable" in result.stderr or "not a regular file" in result.stderr


def test_release_leaves_the_last_holder_pid_recorded(tmp_path: Path) -> None:
    lock_file = tmp_path / "gate.lock"

    first = _run([sys.executable, "-c", "print('first')"], lock_path=lock_file)

    assert first.returncode == 0
    assert "acquired after" not in first.stderr  # uncontended: no wait message
    recorded = lock_file.read_text().strip()
    assert recorded.isdigit()  # the PID stays on record instead of being blanked
