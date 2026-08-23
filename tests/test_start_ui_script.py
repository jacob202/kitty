from __future__ import annotations

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
START_UI = ROOT / "scripts" / "desktop" / "start_ui.sh"
LOAD_ENV = ROOT / "gateway" / "lib" / "load_env_safe.sh"

# start_ui.sh resolves its repo root from its own location, so the real script is
# copied into a throwaway tree rather than pointed at the checkout. That keeps the
# assertions about the shipped file while leaving the developer's .next alone.


def _write_executable(path: Path, body: str) -> None:
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)


def _fake_repo(tmp_path: Path, *, build_id: bool) -> Path:
    root = tmp_path / "repo"
    (root / "scripts" / "desktop").mkdir(parents=True)
    (root / "gateway" / "lib").mkdir(parents=True)
    ui = root / "gateway" / "kitty-chat" / "src"
    ui.mkdir(parents=True)

    (root / "scripts" / "desktop" / "start_ui.sh").write_text(
        START_UI.read_text(encoding="utf-8"), encoding="utf-8"
    )
    (root / "gateway" / "lib" / "load_env_safe.sh").write_text(
        LOAD_ENV.read_text(encoding="utf-8"), encoding="utf-8"
    )
    (ui / "page.tsx").write_text("export default function Page() {}\n", encoding="utf-8")
    (root / "gateway" / "kitty-chat" / "package.json").write_text("{}\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "Kitty Test"], cwd=root, check=True)
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(["git", "commit", "-qm", "fixture"], cwd=root, check=True)

    if build_id:
        next_dir = root / "gateway" / "kitty-chat" / ".next"
        next_dir.mkdir()
        (next_dir / "BUILD_ID").write_text("test-build\n", encoding="utf-8")

    return root


def _set_build_newer_than_source(root: Path) -> None:
    ui = root / "gateway" / "kitty-chat"
    os.utime(ui / "src", (1_000_000, 1_000_000))
    os.utime(ui / "src" / "page.tsx", (1_000_000, 1_000_000))
    os.utime(ui / "package.json", (1_000_000, 1_000_000))
    os.utime(ui / ".next" / "BUILD_ID", (2_000_000, 2_000_000))


def _set_source_newer_than_build(root: Path) -> None:
    ui = root / "gateway" / "kitty-chat"
    os.utime(ui / ".next" / "BUILD_ID", (1_000_000, 1_000_000))
    os.utime(ui / "src", (2_000_000, 2_000_000))
    os.utime(ui / "src" / "page.tsx", (2_000_000, 2_000_000))


def _run(root: Path, tmp_path: Path, *, build_succeeds: bool = True) -> tuple[
    subprocess.CompletedProcess[str], list[str]
]:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir(exist_ok=True)
    call_log = tmp_path / "npm-calls.log"
    build_exit = 0 if build_succeeds else 1
    # A successful build refreshes BUILD_ID the way `next build` does, so a second
    # run of the script sees a current build instead of rebuilding forever.
    _write_executable(
        fake_bin / "npm",
        f"""#!/bin/bash
echo "npm $*" >> "{call_log}"
if [[ "$1" == "run" && "$2" == "build" ]]; then
  if [[ {build_exit} -eq 0 ]]; then
    mkdir -p .next && touch .next/BUILD_ID
  fi
  exit {build_exit}
fi
exit 0
""",
    )

    env = {
        **os.environ,
        "HOME": str(tmp_path),
        "PATH": f"{fake_bin}:/usr/bin:/bin",
    }
    result = subprocess.run(
        ["bash", str(root / "scripts" / "desktop" / "start_ui.sh")],
        capture_output=True,
        text=True,
        env=env,
    )
    calls = call_log.read_text(encoding="utf-8").splitlines() if call_log.exists() else []
    return result, calls


def test_current_build_starts_without_rebuilding(tmp_path):
    root = _fake_repo(tmp_path, build_id=True)
    _set_build_newer_than_source(root)

    result, calls = _run(root, tmp_path)

    assert result.returncode == 0
    assert "build is current" in result.stdout
    assert not any("run build" in call for call in calls)
    assert any("run start" in call for call in calls)


def test_source_newer_than_build_triggers_rebuild(tmp_path):
    root = _fake_repo(tmp_path, build_id=True)
    _set_source_newer_than_build(root)

    result, calls = _run(root, tmp_path)

    assert result.returncode == 0
    assert "is newer than the last build" in result.stdout
    assert calls[0].startswith("npm run build")
    assert any("run start" in call for call in calls)


def test_rebuild_clears_staleness_for_the_next_launch(tmp_path):
    root = _fake_repo(tmp_path, build_id=True)
    _set_source_newer_than_build(root)

    first, first_calls = _run(root, tmp_path)
    second, second_calls = _run(root, tmp_path)

    assert first.returncode == 0
    assert second.returncode == 0
    assert any("run build" in call for call in first_calls)
    # The log accumulates across both runs, so the second run adding only a start
    # call means it found the refreshed build current.
    assert len(second_calls) == len(first_calls) + 1
    assert "build is current" in second.stdout


def test_missing_build_is_built_before_starting(tmp_path):
    root = _fake_repo(tmp_path, build_id=False)

    result, calls = _run(root, tmp_path)

    assert result.returncode == 0
    assert "no usable build" in result.stdout
    assert calls[0].startswith("npm run build")


def test_failed_build_stops_the_service_instead_of_serving_stale_code(tmp_path):
    root = _fake_repo(tmp_path, build_id=True)
    _set_source_newer_than_build(root)

    result, calls = _run(root, tmp_path, build_succeeds=False)

    assert result.returncode != 0
    assert not any("run start" in call for call in calls)


def test_successful_rebuild_records_exact_source_sha(tmp_path):
    root = _fake_repo(tmp_path, build_id=False)
    expected_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    result, _ = _run(root, tmp_path)

    assert result.returncode == 0
    stamp = root / "gateway" / "kitty-chat" / ".next" / "KITTY_SOURCE_SHA"
    assert stamp.read_text(encoding="utf-8").strip() == expected_sha
