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

# Hygiene gates the Tests workflow's `hygiene` job runs that the local gates
# used to omit. The hook/Makefile must run the same tools over the same paths
# so a green local push is not rejected by CI.
VULTURE_CMD = "vulture gateway/ --min-confidence 80 --exclude gateway/kitty-chat/"
LYCHEE_CMD = "lychee --root-dir docs --no-progress --accept 200,301,302,307,308 docs/"
# The hook resolves the lychee binary separately, so only the args string is
# shared verbatim between the workflow and the local gates.
LYCHEE_ARGS = "--root-dir docs --no-progress --accept 200,301,302,307,308 docs/"


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


@pytest.fixture(scope="module")
def workflow_lychee_args() -> str:
    """The hygiene job runs lychee through lycheeverse/lychee-action's `args`."""
    workflow = yaml.safe_load(TESTS_WORKFLOW.read_text(encoding="utf-8"))
    for job in workflow["jobs"].values():
        for step in job.get("steps", []):
            if "lychee" in (step.get("uses") or ""):
                return (step.get("with") or {}).get("args", "")
    raise AssertionError("tests.yml no longer runs lychee; update this test and the hook")


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


def test_vulture_gate_matches_the_workflow(hook_text, workflow_steps):
    """CI's dead-code gate must run locally with the same paths and threshold."""
    assert "vulture gateway/ --min-confidence 80" in workflow_steps, (
        "tests.yml vulture command changed; update this test and the hook"
    )
    assert "--exclude gateway/kitty-chat/" in workflow_steps, (
        "tests.yml vulture exclude changed; update this test and the hook"
    )
    assert VULTURE_CMD in hook_text, "pre-push omits the vulture gate CI enforces"


def test_lychee_gate_matches_the_workflow(hook_text, workflow_lychee_args):
    """CI's link-check gate must run locally with the same paths and accepts."""
    assert workflow_lychee_args == LYCHEE_ARGS, (
        "tests.yml lychee args changed; update this test and the hook"
    )
    assert LYCHEE_ARGS in hook_text, "pre-push omits the lychee gate CI enforces"


def test_make_ci_runs_the_hygiene_gates():
    """`make ci` must include vulture and lychee without dropping the old targets."""
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    ci_line = next(line for line in makefile.splitlines() if line.startswith("ci:"))
    for target in ("lint", "typecheck", "vulture", "lychee", "test-ci", "ui-test", "ui-build"):
        assert target in ci_line, f"`make ci` no longer runs {target}"
    assert VULTURE_CMD in makefile, "`make vulture` diverged from the workflow command"
    assert LYCHEE_CMD in makefile, "`make lychee` diverged from the workflow command"
    assert "vulture" in makefile.split("\n", 1)[0], "`vulture` missing from .PHONY"
    assert "lychee" in makefile.split("\n", 1)[0], "`lychee` missing from .PHONY"


def test_missing_lychee_blocks_the_push():
    """CI checks links on every push; the hook must fail closed, not skip."""
    bash = shutil.which("bash")
    assert bash, "bash is required to run the hook"
    python_bin = shutil.which("python")
    assert python_bin, "a python is required for this test"
    env = {
        **os.environ,
        "PYTHON_BIN": python_bin,
        # /usr/bin:/bin has no lychee; PYTHON_BIN is absolute so the
        # interpreter check passes and the lychee check is the one exercised.
        "PATH": "/usr/bin:/bin",
    }
    result = subprocess.run(
        [bash, str(HOOK)], capture_output=True, text=True, env=env, cwd=ROOT, timeout=60
    )
    assert result.returncode != 0, "hook exited 0 with no lychee installed"
    assert "Push blocked" in result.stderr
    assert "lychee" in result.stderr


def test_frontend_gates_are_present(hook_text):
    """Skipping them when the frontend is untouched is fine; omitting them is not."""
    assert "vitest run" in hook_text
    assert "next build" in hook_text
    assert "gateway/kitty-chat/" in hook_text, "hook has no way to tell whether the frontend changed"


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
    assert "core.hooksPath scripts/hooks" in makefile
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


def test_dead_archive_url_is_not_suppressed_after_repair():
    ignore = (ROOT / ".lycheeignore").read_text(encoding="utf-8")
    assert "svd-ai-lab/open-engineer" not in ignore


def test_hygiene_tool_preflights_fail_loud(hook_text):
    assert "vulture (dead-code checker) is not installed" in hook_text
    assert "lychee (link checker) is not installed" in hook_text


def test_local_lychee_uses_authenticated_github_parity(hook_text):
    assert "gh auth token" in hook_text
    assert "export GITHUB_TOKEN" in hook_text
    assert "no GitHub token is available for the lychee parity gate" in hook_text
