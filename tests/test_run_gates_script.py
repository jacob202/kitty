from pathlib import Path
import os
import subprocess


def test_run_gates_invokes_offline_eval_loop_by_default():
    script = (Path(__file__).resolve().parents[1] / "scripts" / "run_gates.sh").read_text(encoding="utf-8")
    assert "scripts/check_continuity_state.py --max-age-days 21" in script
    assert 'if [[ "${RUN_GATES_SKIP_EVAL_LOOP:-0}" != "1" ]]; then' in script
    assert 'scripts/eval_loop.py --max-attempts 1 --offline' in script


def _run_with_fake_python(tmp_path: Path, *, skip_eval: bool) -> str:
    repo_root = Path(__file__).resolve().parents[1]
    fake_python = tmp_path / "fake-python.sh"
    call_log = tmp_path / "calls.log"
    fake_python.write_text(
        "#!/usr/bin/env bash\n"
        f"echo \"$@\" >> {call_log}\n"
        "exit 0\n",
        encoding="utf-8",
    )
    fake_python.chmod(0o755)

    env = dict(os.environ)
    env["PYTHON_BIN"] = str(fake_python)
    if skip_eval:
        env["RUN_GATES_SKIP_EVAL_LOOP"] = "1"
    else:
        env.pop("RUN_GATES_SKIP_EVAL_LOOP", None)

    subprocess.run(
        ["bash", "scripts/run_gates.sh"],
        cwd=repo_root,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    return call_log.read_text(encoding="utf-8")


def test_run_gates_behavior_default_invokes_eval_loop(tmp_path):
    calls = _run_with_fake_python(tmp_path, skip_eval=False)
    assert "scripts/eval_loop.py --max-attempts 1 --offline" in calls


def test_run_gates_behavior_skip_env_omits_eval_loop(tmp_path):
    calls = _run_with_fake_python(tmp_path, skip_eval=True)
    assert "scripts/eval_loop.py --max-attempts 1 --offline" not in calls
