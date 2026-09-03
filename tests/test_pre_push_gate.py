"""The pre-push hook is only worth having if it checks what CI checks.

GitHub Actions stopped running on 2026-08-06 and every push since has carried no
verdict. `scripts/hooks/pre-push` is the standing local replacement. A local gate
that has drifted from the workflow is worse than none: it reports a pass the
workflow would have rejected. `make ci` had exactly that drift until #442.

These tests pin the parity — the hook runs the same tools, over the same paths,
against the same coverage floor as `.github/workflows/tests.yml` — and pin the
fail-loud behaviour, so a missing toolchain blocks the push instead of waving it
through.
"""

import os
import re
import shutil
import stat
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).parent.parent
HOOK = ROOT / "scripts/hooks/pre-push"
TESTS_WORKFLOW = ROOT / ".github/workflows/tests.yml"

LINT_PATHS = "gateway/ tests/ mcp/ workers/ scripts/runpod_worker_smoke_test.py"
TYPECHECK_PATHS = "gateway/ mcp/ workers/ scripts/runpod_worker_smoke_test.py"


@pytest.fixture(scope="module")
def hook_text() -> str:
    return HOOK.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def workflow_steps() -> str:
    workflow = yaml.safe_load(TESTS_WORKFLOW.read_text(encoding="utf-8"))
    runs = []
    for job in workflow["jobs"].values():
        for step in job.get("steps", []):
            if step.get("run"):
                runs.append(step["run"])
    return "\n".join(runs)


def test_hook_is_executable():
    """git silently ignores a hook without the execute bit."""
    assert HOOK.exists(), "scripts/hooks/pre-push is missing"
    assert HOOK.stat().st_mode & stat.S_IXUSR, "pre-push hook is not executable"


def test_lint_paths_match_the_workflow(hook_text, workflow_steps):
    assert LINT_PATHS in workflow_steps, "tests.yml ruff paths changed; update this test and the hook"
    assert LINT_PATHS in hook_text, "pre-push lints narrower than CI, so it can pass code CI rejects"


def test_typecheck_paths_match_the_workflow(hook_text, workflow_steps):
    assert TYPECHECK_PATHS in workflow_steps, "tests.yml mypy paths changed; update this test and the hook"
    assert TYPECHECK_PATHS in hook_text, "pre-push typechecks narrower than CI"


def test_coverage_floor_matches_the_workflow(hook_text, workflow_steps):
    workflow_floor = re.search(r"--cov-fail-under=(\d+)", workflow_steps)
    hook_floor = re.search(r"--cov-fail-under=(\d+)", hook_text)
    assert workflow_floor, "tests.yml no longer sets a coverage floor"
    assert hook_floor, "pre-push runs pytest without the coverage floor CI enforces"
    assert hook_floor.group(1) == workflow_floor.group(1), (
        f"coverage floor drifted: workflow {workflow_floor.group(1)}%, hook {hook_floor.group(1)}%"
    )


def test_frontend_gates_are_present(hook_text):
    """Skipping them when the frontend is untouched is fine; omitting them is not."""
    assert "vitest run" in hook_text
    assert "next build" in hook_text
    assert "gateway/kitty-chat/" in hook_text, "hook has no way to tell whether the frontend changed"


def test_local_frontend_gate_bounds_vitest_workers(hook_text):
    """The 8 GB local host must not fan out enough JSDOM workers to fake timeouts."""
    web_gate = next(line for line in hook_text.splitlines() if 'run_gate "web tests"' in line)
    assert "--maxWorkers=2" in web_gate


def test_frontend_gates_run_before_memory_heavy_python_suite(hook_text):
    """On the 8 GB Mac, coverage first can push Vitest into swap and fake timeouts."""
    assert hook_text.index('run_gate "web tests"') < hook_text.index('run_gate "tests"')
    assert hook_text.index('run_gate "web build"') < hook_text.index('run_gate "tests"')


def test_python_gates_never_skip(hook_text):
    """Both breakages that reddened main on 2026-08-09 were docs-only changes."""
    guard = hook_text.split("RUN_FRONTEND=1", 1)[1]
    pytest_call = guard.split("-m pytest", 1)
    assert len(pytest_call) == 2, "pytest is not invoked after the frontend decision"
    assert "RUN_FRONTEND" not in pytest_call[0].rsplit("run_gate", 1)[-1], (
        "pytest sits behind the frontend-changed condition; docs-only pushes would skip it"
    )


def test_missing_interpreter_blocks_the_push(tmp_path):
    """A gate that cannot run must fail closed, never report a pass it did not check."""
    bash = shutil.which("bash")
    assert bash, "bash is required to run the hook"
    # An empty PATH is what makes python3.12 unfindable; bash is invoked by
    # absolute path so the test exercises the interpreter check, not a missing shell.
    env = {
        **os.environ,
        "PYTHON_BIN": str(tmp_path / "definitely-not-here"),
        "PATH": str(tmp_path),
    }
    result = subprocess.run(
        [bash, str(HOOK)], capture_output=True, text=True, env=env, cwd=ROOT, timeout=60
    )
    assert result.returncode != 0, "hook exited 0 with no usable Python"
    assert "Push blocked" in result.stderr


def test_make_hooks_points_git_at_the_hook_directory():
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    assert "\nhooks:" in makefile, "no `make hooks` target to install the gate"
    assert "core.hooksPath .githooks" in makefile
    assert "hooks" in makefile.split("\n", 1)[0], "`hooks` missing from .PHONY"


def test_make_hooks_configures_ssh_keepalive_without_overwriting_custom_command(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)

    subprocess.run(["make", "-f", str(ROOT / "Makefile"), "hooks"], cwd=repo, check=True)
    configured = subprocess.run(
        ["git", "config", "--get", "core.sshCommand"],
        cwd=repo, capture_output=True, text=True, check=True,
    ).stdout.strip()
    assert "ServerAliveInterval=30" in configured
    assert "ServerAliveCountMax=30" in configured

    custom = "ssh -F /tmp/custom-ssh-config"
    subprocess.run(["git", "config", "core.sshCommand", custom], cwd=repo, check=True)
    subprocess.run(["make", "-f", str(ROOT / "Makefile"), "hooks"], cwd=repo, check=True)
    preserved = subprocess.run(
        ["git", "config", "--get", "core.sshCommand"],
        cwd=repo, capture_output=True, text=True, check=True,
    ).stdout.strip()
    assert preserved == custom


def test_hook_clears_git_local_env_before_gates(hook_text):
    """Nested git commands in pytest must not inherit the pushing repo's GIT_* vars."""
    clear_marker = "git rev-parse --local-env-vars"
    assert clear_marker in hook_text, "pre-push leaks Git's local environment into pytest"
    assert hook_text.index(clear_marker) < hook_text.index('run_gate "code style"')


def test_linked_worktree_uses_canonical_repo_venv_before_system_python(hook_text):
    """Builder worktrees must use the canonical Kitty venv, matching CI deps."""
    assert "--git-common-dir" in hook_text
    assert "CANONICAL_ROOT" in hook_text
    canonical_venv = '${CANONICAL_ROOT}/venv/bin/python'
    assert canonical_venv in hook_text
    assert hook_text.index(canonical_venv) < hook_text.index("python3.12")


def test_hook_clears_builder_data_dir_before_gates(hook_text):
    """Builder-local DB routing must not leak into CI-parity tests."""
    clear_marker = "unset KITTY_BUILDER_DATA_DIR"
    assert clear_marker in hook_text, "pre-push leaks Builder's proof DB override into pytest"
    assert hook_text.index(clear_marker) < hook_text.index('run_gate "code style"')


def test_preflight_checks_environment_without_running_quality_gates(tmp_path):
    fake_python = tmp_path / "python"
    fake_python.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    fake_python.chmod(0o755)
    result = subprocess.run(
        [str(HOOK), "--preflight"],
        cwd=ROOT,
        env={**os.environ, "PYTHON_BIN": str(fake_python)},
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    assert "preflight passed" in result.stderr
    assert "Checking before push" not in result.stderr


def test_full_gate_preserves_infrastructure_exit_class(hook_text):
    assert "INFRA_FAILED=0" in hook_text
    assert "gate_rc} -eq 75" in hook_text
    assert "gate_rc} -eq 126" in hook_text
    assert "gate_rc} -eq 127" in hook_text
    assert 'if [[ "${INFRA_FAILED}" == "1" ]]' in hook_text
    assert "exit 75" in hook_text


def test_hook_accepts_gits_remote_name_and_url_arguments(hook_text):
    assert 'REMOTE_NAME="${1:-}"' in hook_text
    assert 'REMOTE_URL="${2:-}"' in hook_text
    assert "Git invokes pre-push as: <hook> <remote-name> <remote-url>" in hook_text


def test_hook_blocks_direct_main_push_without_explicit_override(hook_text):
    assert "refs/heads/main" in hook_text
    assert "KITTY_ALLOW_DIRECT_MAIN_PUSH" in hook_text
    assert hook_text.index("refs/heads/main") < hook_text.index("Checking before push")


def test_real_disposable_git_push_accepts_standard_hook_arguments(tmp_path):
    """A normal `git push` must invoke the hook with Git's remote name/URL contract."""
    repo = tmp_path / "repo"
    remote = tmp_path / "remote.git"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "init", "--bare", "-q", str(remote)], check=True)
    subprocess.run(["git", "config", "user.name", "Kitty Test"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "kitty-test@example.invalid"], cwd=repo, check=True)

    (repo / "README.md").write_text("seed\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "seed"], cwd=repo, check=True)
    subprocess.run(["git", "branch", "-M", "main"], cwd=repo, check=True)
    subprocess.run(["git", "remote", "add", "origin", str(remote)], cwd=repo, check=True)
    subprocess.run(["git", "push", "--no-verify", "-u", "origin", "main"], cwd=repo, check=True)

    hook_source = Path(os.environ.get("KITTY_PRE_PUSH_HOOK_UNDER_TEST", HOOK))
    hook = repo / "scripts" / "hooks" / "pre-push"
    hook.parent.mkdir(parents=True)
    shutil.copy2(hook_source, hook)
    hook.chmod(hook.stat().st_mode | stat.S_IXUSR)
    subprocess.run(["git", "config", "core.hooksPath", "scripts/hooks"], cwd=repo, check=True)

    fake_python = tmp_path / "python"
    fake_python.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    fake_python.chmod(0o755)

    subprocess.run(["git", "switch", "-qc", "feature"], cwd=repo, check=True)
    (repo / "README.md").write_text("seed\nfeature\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "feature"], cwd=repo, check=True)

    result = subprocess.run(
        ["git", "push", "-u", "origin", "feature"],
        cwd=repo,
        env={**os.environ, "PYTHON_BIN": str(fake_python)},
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    assert "All clear" in result.stderr
    pushed = subprocess.run(
        ["git", "--git-dir", str(remote), "rev-parse", "refs/heads/feature"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    assert pushed


def test_relative_hooks_path_uses_linked_worktree_hook(tmp_path):
    """Linked worktrees must execute their own tracked hook, not a canonical checkout copy."""
    repo = tmp_path / "repo"
    worktree = tmp_path / "worktree"
    remote = tmp_path / "remote.git"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "init", "--bare", "-q", str(remote)], check=True)
    subprocess.run(["git", "config", "user.name", "Kitty Test"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "kitty-test@example.invalid"], cwd=repo, check=True)
    (repo / "README.md").write_text("seed\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "seed"], cwd=repo, check=True)
    subprocess.run(["git", "branch", "-M", "main"], cwd=repo, check=True)
    subprocess.run(["git", "remote", "add", "origin", str(remote)], cwd=repo, check=True)
    subprocess.run(["git", "push", "--no-verify", "-u", "origin", "main"], cwd=repo, check=True)
    subprocess.run(["git", "worktree", "add", "-qb", "feature", str(worktree), "main"], cwd=repo, check=True)

    canonical_hook = repo / "scripts" / "hooks" / "pre-push"
    canonical_hook.parent.mkdir(parents=True)
    canonical_hook.write_text("#!/bin/sh\necho CANONICAL >&2\nexit 13\n", encoding="utf-8")
    canonical_hook.chmod(0o755)
    worktree_hook = worktree / "scripts" / "hooks" / "pre-push"
    worktree_hook.parent.mkdir(parents=True)
    worktree_hook.write_text("#!/bin/sh\necho WORKTREE >&2\nexit 0\n", encoding="utf-8")
    worktree_hook.chmod(0o755)
    subprocess.run(["git", "config", "core.hooksPath", "scripts/hooks"], cwd=repo, check=True)

    (worktree / "README.md").write_text("seed\nfeature\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=worktree, check=True)
    subprocess.run(["git", "commit", "-qm", "feature"], cwd=worktree, check=True)
    result = subprocess.run(
        ["git", "push", "-u", "origin", "feature"],
        cwd=worktree,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    assert "WORKTREE" in result.stderr
    assert "CANONICAL" not in result.stderr
