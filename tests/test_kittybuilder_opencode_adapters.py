"""Contract tests for the free OpenCode KittyBuilder adapter scripts."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / "scripts" / "kittybuilder_opencode_worker.sh"
REVIEWER = ROOT / "scripts" / "kittybuilder_opencode_reviewer.sh"
TIMEOUT_RUNNER = ROOT / "scripts" / "run_with_timeout.py"


def _manifest(bundle: Path, *, task_id: str = "task-1", attempt_id: str = "7") -> Path:
    digest = hashlib.sha256(bundle.read_bytes()).hexdigest()
    path = bundle.parent / "run-manifest.json"
    path.write_text(
        json.dumps(
            {
                "manifest_version": 1,
                "task_id": task_id,
                "attempt_id": int(attempt_id),
                "bundle_sha256": digest,
                "context": {"task_bundle": {"sha256": digest}},
            }
        ),
        encoding="utf-8",
    )
    return path


def _fake_opencode(tmp_path: Path) -> Path:
    fake = tmp_path / "opencode"
    fake.write_text(
        f"#!{sys.executable}\n"
        + """import json
import os
import re
import sys
from pathlib import Path

args = sys.argv
model = args[args.index("--model") + 1] if "--model" in args else ""
agent = args[args.index("--agent") + 1] if "--agent" in args else ""
agent_log = os.environ.get("FAKE_OPENCODE_AGENT_LOG", "")
if agent_log:
    Path(agent_log).write_text(agent, encoding="utf-8")
model_log = os.environ.get("FAKE_OPENCODE_MODEL_LOG", "")
if model_log:
    Path(model_log).write_text(model, encoding="utf-8")
if os.environ.get("FAKE_OPENCODE_READ_STDIN"):
    sys.stdin.read()
fail_models = set(
    filter(None, os.environ.get("FAKE_OPENCODE_FAIL_MODELS", "").split(","))
)
if model in fail_models:
    if os.environ.get("FAKE_OPENCODE_FAIL_MUTATE"):
        Path("partial-work.txt").write_text("partial\\n", encoding="utf-8")
    raise SystemExit(1)
hang_models = set(
    filter(None, os.environ.get("FAKE_OPENCODE_HANG_MODELS", "").split(","))
)
if model in hang_models:
    import time

    time.sleep(float(os.environ.get("FAKE_OPENCODE_HANG_SECONDS", "2")))
prompt = args[-1]
prompt_log = os.environ.get("FAKE_OPENCODE_PROMPT_LOG", "")
if prompt_log:
    Path(prompt_log).write_text(prompt, encoding="utf-8")
match = re.search(r"[Ww]rite a JSON object to (.+?) with exactly", prompt)
if not match:
    raise SystemExit("prompt did not contain a contract output path")
output = Path(match.group(1))
if os.environ.get("FAKE_OPENCODE_MUTATE"):
    Path("reviewer-mutated.txt").write_text("mutation\\n", encoding="utf-8")
if os.environ.get("FAKE_OPENCODE_CONTINUATION"):
    continuation = Path(".omo/run-continuation/session.json")
    continuation.parent.mkdir(parents=True, exist_ok=True)
    continuation.write_text("runtime receipt\\n", encoding="utf-8")
if os.environ.get("FAKE_OPENCODE_IMPLEMENT_CHANGE"):
    Path("implemented.txt").write_text("real change\\n", encoding="utf-8")
if os.environ.get("FAKE_OPENCODE_REVIEW"):
    payload = {"contract_version": 1, "verdict": "approve", "summary": "ok"}
else:
    status = os.environ.get("FAKE_OPENCODE_STATUS", "completed")
    payload = {"contract_version": 1, "status": status, "summary": "ok"}
output.write_text(json.dumps(payload), encoding="utf-8")
""",
        encoding="utf-8",
    )
    fake.chmod(0o755)
    return fake


def _init_git_repo(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("adapter test\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Adapter Test"], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", "README.md"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=tmp_path, check=True)


def _env(fake: Path, *, bundle: Path, context: Path, result: Path) -> dict[str, str]:
    env = dict(os.environ)
    env.update(
        {
            "PATH": f"{fake.parent}:{env['PATH']}",
            "KB_BUNDLE_PATH": str(bundle),
            "KB_CONTEXT_MANIFEST_PATH": str(context),
            "KB_RESULT_PATH": str(result),
            "KB_ATTEMPT_ID": "7",
            "KB_TASK_ID": "task-1",
            "PYTHONUNBUFFERED": "1",
        }
    )
    return env


def _review_binding(tmp_path: Path, *, task_id: str = "task-1", attempt_id: int = 7) -> Path:
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=tmp_path, check=True,
        capture_output=True, text=True,
    ).stdout.strip()
    path = tmp_path / "review-context.json"
    path.write_text(
        json.dumps(
            {
                "task_id": task_id,
                "attempt_id": attempt_id,
                "review_sha": head,
                "diff_sha256": "0" * 64,
                "changed_paths": [],
            }
        ),
        encoding="utf-8",
    )
    return path



def test_timeout_runner_kills_descendant_process_group(tmp_path: Path):
    child_pid = tmp_path / "child.pid"
    script = tmp_path / "spawn-child.sh"
    script.write_text(
        '#!/bin/sh\nsleep 30 &\necho "$!" > "$1"\nwait\n',
        encoding="utf-8",
    )
    script.chmod(0o755)

    completed = subprocess.run(
        [sys.executable, str(TIMEOUT_RUNNER), "1", str(script), str(child_pid)],
        capture_output=True,
        text=True,
        timeout=5,
    )

    assert completed.returncode == 124
    pid = int(child_pid.read_text())
    for _ in range(20):
        state = subprocess.run(
            ["ps", "-p", str(pid), "-o", "stat="],
            capture_output=True,
            text=True,
        ).stdout.strip()
        if not state or state.startswith("Z"):
            break
        time.sleep(0.05)
    else:
        raise AssertionError(f"timed-out descendant {pid} is still running: {state}")



def test_timeout_runner_closes_child_stdin_when_parent_stdin_stays_open(tmp_path: Path):
    marker = tmp_path / "stdin-eof.txt"
    script = tmp_path / "read-stdin.py"
    script.write_text(
        "import sys\nfrom pathlib import Path\nsys.stdin.read()\nPath(sys.argv[1]).write_text('eof\\n', encoding='utf-8')\n",
        encoding="utf-8",
    )

    proc = subprocess.Popen(
        [sys.executable, str(TIMEOUT_RUNNER), "1", sys.executable, str(script), str(marker)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        returncode = proc.wait(timeout=3)
        stdout = proc.stdout.read() if proc.stdout else ""
        stderr = proc.stderr.read() if proc.stderr else ""
    finally:
        if proc.stdin:
            proc.stdin.close()

    assert returncode == 0, f"stdout={stdout!r} stderr={stderr!r}"
    assert marker.read_text(encoding="utf-8") == "eof\n"

def test_timeout_runner_forwards_outer_termination_to_descendants(tmp_path: Path):
    child_pid = tmp_path / "outer-child.pid"
    script = tmp_path / "spawn-outer-child.sh"
    script.write_text(
        '#!/bin/sh\nsleep 30 &\necho "$!" > "$1"\nwait\n',
        encoding="utf-8",
    )
    script.chmod(0o755)

    proc = subprocess.Popen(
        [sys.executable, str(TIMEOUT_RUNNER), "30", str(script), str(child_pid)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    for _ in range(50):
        if child_pid.exists():
            break
        time.sleep(0.02)
    else:
        proc.kill()
        raise AssertionError("timeout helper never started its descendant")

    pid = int(child_pid.read_text())
    proc.terminate()
    proc.wait(timeout=5)
    assert proc.returncode != 0
    for _ in range(20):
        state = subprocess.run(
            ["ps", "-p", str(pid), "-o", "stat="],
            capture_output=True,
            text=True,
        ).stdout.strip()
        if not state or state.startswith("Z"):
            break
        time.sleep(0.05)
    else:
        raise AssertionError(f"outer termination left descendant {pid} running: {state}")


def test_worker_stages_and_validates_local_context(tmp_path: Path):
    _init_git_repo(tmp_path)
    bundle = tmp_path / "bundle.json"
    bundle.write_text('{"objective":"safe","packet_id":"pkt-1"}\n', encoding="utf-8")
    context = _manifest(bundle)
    result = tmp_path / "runner" / "implementation.json"
    result.parent.mkdir()
    fake = _fake_opencode(tmp_path)

    completed = subprocess.run(
        [str(WORKER)],
        cwd=tmp_path,
        env=_env(fake, bundle=bundle, context=context, result=result),
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert json.loads(result.read_text()) ["status"] == "completed"
    assert not list(tmp_path.glob(".kittybuilder-*"))


def test_worker_result_handoff_does_not_depend_on_cp_metadata_copy(tmp_path: Path):
    _init_git_repo(tmp_path)
    bundle = tmp_path / "bundle.json"
    bundle.write_text('{"objective":"safe","packet_id":"pkt-1"}\n', encoding="utf-8")
    context = _manifest(bundle)
    result = tmp_path / "runner" / "implementation.json"
    result.parent.mkdir()
    fake = _fake_opencode(tmp_path)
    fake_cp = tmp_path / "cp"
    fake_cp.write_text(
        "#!/bin/sh\n"
        "case \"$2\" in\n"
        "  */implementation.json) echo \"cp: $2: Operation not permitted\" >&2; exit 1 ;;\n"
        "esac\n"
        "exec /bin/cp \"$@\"\n",
        encoding="utf-8",
    )
    fake_cp.chmod(0o755)

    completed = subprocess.run(
        [str(WORKER)],
        cwd=tmp_path,
        env=_env(fake, bundle=bundle, context=context, result=result),
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert json.loads(result.read_text(encoding="utf-8"))["status"] == "completed"


def test_worker_delegates_declared_validation_to_trusted_builder(tmp_path: Path):
    _init_git_repo(tmp_path)
    bundle = tmp_path / "bundle.json"
    bundle.write_text(
        '{"objective":"safe","packet_id":"pkt-1","validation_commands":["python -m pytest -q"]}\n',
        encoding="utf-8",
    )
    context = _manifest(bundle)
    result = tmp_path / "runner" / "implementation.json"
    result.parent.mkdir()
    fake = _fake_opencode(tmp_path)
    prompt_log = tmp_path / "prompt.txt"
    env = _env(fake, bundle=bundle, context=context, result=result)
    env["FAKE_OPENCODE_PROMPT_LOG"] = str(prompt_log)

    completed = subprocess.run(
        [str(WORKER)], cwd=tmp_path, env=env, capture_output=True, text=True
    )

    assert completed.returncode == 0, completed.stderr
    prompt = prompt_log.read_text(encoding="utf-8")
    assert "trusted Builder orchestration runs the declared validation commands" in prompt
    assert "Run the declared validation commands" not in prompt


def test_worker_leaves_completed_change_for_trusted_parent_commit(tmp_path: Path):
    """The model adapter may edit the worktree but cannot mutate Git metadata.

    Trusted Builder orchestration commits a validated completed result before
    review, so the adapter must leave the model's real change uncommitted.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_git_repo(repo)
    before_head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, check=True,
        capture_output=True, text=True,
    ).stdout.strip()
    bundle = tmp_path / "bundle.json"
    bundle.write_text(
        '{"objective":"safe","packet_id":"pkt-1"}\n', encoding="utf-8"
    )
    context = _manifest(bundle)
    result = tmp_path / "runner" / "implementation.json"
    result.parent.mkdir()
    fake = _fake_opencode(tmp_path)
    env = _env(fake, bundle=bundle, context=context, result=result)
    env["FAKE_OPENCODE_IMPLEMENT_CHANGE"] = "1"

    completed = subprocess.run(
        [str(WORKER)], cwd=repo, env=env, capture_output=True, text=True,
    )

    assert completed.returncode == 0, completed.stderr
    status = subprocess.run(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"],
        cwd=repo, check=True, capture_output=True, text=True,
    ).stdout
    assert status.split() == ["??", "implemented.txt"]
    after_head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, check=True,
        capture_output=True, text=True,
    ).stdout.strip()
    assert after_head == before_head


def test_worker_does_not_commit_a_failed_result(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_git_repo(repo)
    before_head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, check=True,
        capture_output=True, text=True,
    ).stdout.strip()
    bundle = tmp_path / "bundle.json"
    bundle.write_text('{"objective":"safe","packet_id":"pkt-1"}\n', encoding="utf-8")
    context = _manifest(bundle)
    result = tmp_path / "runner" / "implementation.json"
    result.parent.mkdir()
    fake = _fake_opencode(tmp_path)
    env = _env(fake, bundle=bundle, context=context, result=result)
    env["FAKE_OPENCODE_IMPLEMENT_CHANGE"] = "1"
    env["FAKE_OPENCODE_STATUS"] = "failed"

    completed = subprocess.run(
        [str(WORKER)], cwd=repo, env=env, capture_output=True, text=True,
    )

    assert completed.returncode == 0, completed.stderr
    after_head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, check=True,
        capture_output=True, text=True,
    ).stdout.strip()
    assert after_head == before_head
    # The failed attempt's evidence (the uncommitted file) stays visible for
    # inspection, not silently committed or discarded.
    assert (repo / "implemented.txt").exists()


def test_worker_rejects_mismatched_context_before_opencode(tmp_path: Path):
    _init_git_repo(tmp_path)
    bundle = tmp_path / "bundle.json"
    bundle.write_text('{"objective":"safe","packet_id":"pkt-1"}\n', encoding="utf-8")
    context = tmp_path / "run-manifest.json"
    context.write_text(
        json.dumps(
            {
                "task_id": "task-1",
                "attempt_id": 7,
                "bundle_sha256": "wrong",
                "context": {"task_bundle": {"sha256": "wrong"}},
            }
        ),
        encoding="utf-8",
    )
    result = tmp_path / "implementation.json"
    fake = _fake_opencode(tmp_path)

    completed = subprocess.run(
        [str(WORKER)],
        cwd=tmp_path,
        env=_env(fake, bundle=bundle, context=context, result=result),
        capture_output=True,
        text=True,
    )

    assert completed.returncode != 0
    assert "hash" in completed.stderr
    assert not result.exists()


def test_worker_refuses_to_delete_a_preexisting_staging_file(tmp_path: Path):
    _init_git_repo(tmp_path)
    bundle = tmp_path / "bundle.json"
    bundle.write_text('{"objective":"safe","packet_id":"pkt-1"}\n', encoding="utf-8")
    context = _manifest(bundle)
    result = tmp_path / "implementation.json"
    (tmp_path / ".kittybuilder-bundle-7.json").write_text(
        "user file\n", encoding="utf-8"
    )
    fake = _fake_opencode(tmp_path)

    completed = subprocess.run(
        [str(WORKER)],
        cwd=tmp_path,
        env=_env(fake, bundle=bundle, context=context, result=result),
        capture_output=True,
        text=True,
    )

    assert completed.returncode != 0
    assert "staging path already exists" in completed.stderr
    assert (tmp_path / ".kittybuilder-bundle-7.json").read_text() == "user file\n"
    assert not result.exists()


def test_worker_requires_a_git_worktree(tmp_path: Path):
    bundle = tmp_path / "bundle.json"
    bundle.write_text('{"objective":"safe","packet_id":"pkt-1"}\n', encoding="utf-8")
    context = _manifest(bundle)
    result = tmp_path / "implementation.json"
    fake = _fake_opencode(tmp_path)

    completed = subprocess.run(
        [str(WORKER)],
        cwd=tmp_path,
        env=_env(fake, bundle=bundle, context=context, result=result),
        capture_output=True,
        text=True,
    )

    assert completed.returncode != 0
    assert "isolated git worktree" in completed.stderr
    assert not result.exists()


def test_worker_falls_through_ladder_on_clean_model_failure(tmp_path: Path):
    _init_git_repo(tmp_path)
    bundle = tmp_path / "bundle.json"
    bundle.write_text('{"objective":"safe","packet_id":"pkt-1"}\n', encoding="utf-8")
    context = _manifest(bundle)
    result = tmp_path / "implementation.json"
    fake = _fake_opencode(tmp_path)
    env = _env(fake, bundle=bundle, context=context, result=result)
    env.update(
        {
            "KITTYBUILDER_MODELS": "free-a free-b",
            "FAKE_OPENCODE_FAIL_MODELS": "free-a",
        }
    )

    completed = subprocess.run(
        [str(WORKER)], cwd=tmp_path, env=env, capture_output=True, text=True
    )

    assert completed.returncode == 0, completed.stderr
    assert json.loads(result.read_text())["status"] == "completed"
    assert "trying the next free model" in completed.stderr
    assert "Free builder completed with free-b" in completed.stdout


def test_worker_times_out_silent_model_and_falls_through(tmp_path: Path):
    _init_git_repo(tmp_path)
    bundle = tmp_path / "bundle.json"
    bundle.write_text('{"objective":"safe","packet_id":"pkt-1"}\n', encoding="utf-8")
    context = _manifest(bundle)
    result = tmp_path / "implementation.json"
    fake = _fake_opencode(tmp_path)
    model_log = tmp_path.parent / f"{tmp_path.name}-model-used.txt"
    env = _env(fake, bundle=bundle, context=context, result=result)
    env.update(
        {
            "KITTYBUILDER_MODELS": "free-a free-b",
            "KB_WORKER_TIMEOUT_SECONDS": "2",
            "FAKE_OPENCODE_HANG_MODELS": "free-a",
            "FAKE_OPENCODE_HANG_SECONDS": "3",
            "FAKE_OPENCODE_MODEL_LOG": str(model_log),
        }
    )

    completed = subprocess.run(
        [str(WORKER)], cwd=tmp_path, env=env, capture_output=True, text=True, timeout=8
    )

    assert completed.returncode == 0, completed.stderr
    assert json.loads(result.read_text())["status"] == "completed"
    assert model_log.read_text() == "free-b"
    assert "timed out" in completed.stderr
    assert "trying the next free model" in completed.stderr


def test_worker_never_falls_back_over_partial_work(tmp_path: Path):
    _init_git_repo(tmp_path)
    bundle = tmp_path / "bundle.json"
    bundle.write_text('{"objective":"safe","packet_id":"pkt-1"}\n', encoding="utf-8")
    context = _manifest(bundle)
    result = tmp_path / "implementation.json"
    fake = _fake_opencode(tmp_path)
    env = _env(fake, bundle=bundle, context=context, result=result)
    env.update(
        {
            "KITTYBUILDER_MODELS": "free-a free-b",
            "FAKE_OPENCODE_FAIL_MODELS": "free-a",
            "FAKE_OPENCODE_FAIL_MUTATE": "1",
        }
    )

    completed = subprocess.run(
        [str(WORKER)], cwd=tmp_path, env=env, capture_output=True, text=True
    )

    assert completed.returncode != 0
    assert "no fallback over partial work" in completed.stderr
    assert not result.exists()
    assert (tmp_path / "partial-work.txt").read_text() == "partial\n"


def test_worker_forced_single_model_disables_the_ladder(tmp_path: Path):
    _init_git_repo(tmp_path)
    bundle = tmp_path / "bundle.json"
    bundle.write_text('{"objective":"safe","packet_id":"pkt-1"}\n', encoding="utf-8")
    context = _manifest(bundle)
    result = tmp_path / "implementation.json"
    fake = _fake_opencode(tmp_path)
    env = _env(fake, bundle=bundle, context=context, result=result)
    env.update(
        {
            "KITTYBUILDER_MODEL": "free-a",
            "FAKE_OPENCODE_FAIL_MODELS": "free-a",
        }
    )

    completed = subprocess.run(
        [str(WORKER)], cwd=tmp_path, env=env, capture_output=True, text=True
    )

    assert completed.returncode != 0
    assert "every free model failed" in completed.stderr
    assert not result.exists()


def test_reviewer_copies_only_a_valid_immutable_review(tmp_path: Path):
    _init_git_repo(tmp_path)
    bundle = tmp_path / "bundle.json"
    bundle.write_text('{"objective":"safe","packet_id":"pkt-1"}\n', encoding="utf-8")
    context = _manifest(bundle)
    implementation = tmp_path / "implementation.json"
    implementation.write_text('{"contract_version":1}\n', encoding="utf-8")
    review = tmp_path / "runner" / "review.json"
    review.parent.mkdir()
    fake = _fake_opencode(tmp_path)
    binding = _review_binding(tmp_path)
    env = _env(fake, bundle=bundle, context=context, result=tmp_path / "unused.json")
    env.update(
        {
            "KB_IMPL_RESULT_PATH": str(implementation),
            "KB_REVIEW_RESULT_PATH": str(review),
            "FAKE_OPENCODE_REVIEW": "1",
            "KB_REVIEW_CONTEXT_PATH": str(binding),
            "KB_REVIEW_SHA": subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=tmp_path, check=True,
                capture_output=True, text=True,
            ).stdout.strip(),
            "KB_REVIEW_DIFF_SHA256": "0" * 64,
        }
    )

    completed = subprocess.run(
        [str(REVIEWER)],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert json.loads(review.read_text())["verdict"] == "approve"
    assert not list(tmp_path.glob(".kittybuilder-review-*"))


def test_reviewer_rejects_worktree_mutation_and_does_not_publish_review(tmp_path: Path):
    _init_git_repo(tmp_path)
    bundle = tmp_path / "bundle.json"
    bundle.write_text('{"objective":"safe","packet_id":"pkt-1"}\n', encoding="utf-8")
    context = _manifest(bundle)
    implementation = tmp_path / "implementation.json"
    implementation.write_text('{"contract_version":1}\n', encoding="utf-8")
    review = tmp_path / "review.json"
    fake = _fake_opencode(tmp_path)
    binding = _review_binding(tmp_path)
    env = _env(fake, bundle=bundle, context=context, result=tmp_path / "unused.json")
    env.update(
        {
            "KB_IMPL_RESULT_PATH": str(implementation),
            "KB_REVIEW_RESULT_PATH": str(review),
            "FAKE_OPENCODE_REVIEW": "1",
            "FAKE_OPENCODE_MUTATE": "1",
            "KB_REVIEW_CONTEXT_PATH": str(binding),
            "KB_REVIEW_SHA": subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=tmp_path, check=True,
                capture_output=True, text=True,
            ).stdout.strip(),
            "KB_REVIEW_DIFF_SHA256": "0" * 64,
        }
    )

    completed = subprocess.run(
        [str(REVIEWER)],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
    )

    assert completed.returncode != 0
    assert "changed the worktree" in completed.stderr
    assert not review.exists()


def test_reviewer_allows_opencode_continuation_residue(tmp_path: Path):
    _init_git_repo(tmp_path)
    bundle = tmp_path / "bundle.json"
    bundle.write_text('{"objective":"safe","packet_id":"pkt-1"}\n', encoding="utf-8")
    context = _manifest(bundle)
    implementation = tmp_path / "implementation.json"
    implementation.write_text('{"contract_version":1}\n', encoding="utf-8")
    review = tmp_path / "review.json"
    fake = _fake_opencode(tmp_path)
    binding = _review_binding(tmp_path)
    env = _env(fake, bundle=bundle, context=context, result=tmp_path / "unused.json")
    env.update(
        {
            "KB_IMPL_RESULT_PATH": str(implementation),
            "KB_REVIEW_RESULT_PATH": str(review),
            "FAKE_OPENCODE_REVIEW": "1",
            "FAKE_OPENCODE_CONTINUATION": "1",
            "KB_REVIEW_CONTEXT_PATH": str(binding),
            "KB_REVIEW_SHA": subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=tmp_path, check=True,
                capture_output=True, text=True,
            ).stdout.strip(),
            "KB_REVIEW_DIFF_SHA256": "0" * 64,
        }
    )

    completed = subprocess.run(
        [str(REVIEWER)], cwd=tmp_path, env=env, capture_output=True, text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert json.loads(review.read_text())["verdict"] == "approve"


def test_reviewer_falls_through_ladder_on_clean_model_failure(tmp_path: Path):
    _init_git_repo(tmp_path)
    bundle = tmp_path / "bundle.json"
    bundle.write_text('{"objective":"safe","packet_id":"pkt-1"}\n', encoding="utf-8")
    context = _manifest(bundle)
    implementation = tmp_path / "implementation.json"
    implementation.write_text('{"contract_version":1}\n', encoding="utf-8")
    review = tmp_path / "review.json"
    fake = _fake_opencode(tmp_path)
    binding = _review_binding(tmp_path)
    env = _env(fake, bundle=bundle, context=context, result=tmp_path / "unused.json")
    env.update(
        {
            "KB_IMPL_RESULT_PATH": str(implementation),
            "KB_REVIEW_RESULT_PATH": str(review),
            "FAKE_OPENCODE_REVIEW": "1",
            "KITTYBUILDER_REVIEW_MODELS": "rev-a rev-b",
            "FAKE_OPENCODE_FAIL_MODELS": "rev-a",
            "KB_REVIEW_CONTEXT_PATH": str(binding),
            "KB_REVIEW_SHA": subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=tmp_path, check=True,
                capture_output=True, text=True,
            ).stdout.strip(),
            "KB_REVIEW_DIFF_SHA256": "0" * 64,
        }
    )

    completed = subprocess.run(
        [str(REVIEWER)], cwd=tmp_path, env=env, capture_output=True, text=True
    )

    assert completed.returncode == 0, completed.stderr
    assert json.loads(review.read_text())["verdict"] == "approve"
    assert "trying the next free model" in completed.stderr
    assert "Review completed with rev-b" in completed.stdout


def test_reviewer_times_out_silent_model_and_falls_through(tmp_path: Path):
    _init_git_repo(tmp_path)
    bundle = tmp_path / "bundle.json"
    bundle.write_text('{"objective":"safe","packet_id":"pkt-1"}\n', encoding="utf-8")
    context = _manifest(bundle)
    implementation = tmp_path / "implementation.json"
    implementation.write_text('{"contract_version":1}\n', encoding="utf-8")
    review = tmp_path / "review.json"
    fake = _fake_opencode(tmp_path)
    binding = _review_binding(tmp_path)
    model_log = tmp_path.parent / f"{tmp_path.name}-review-model-used.txt"
    env = _env(fake, bundle=bundle, context=context, result=tmp_path / "unused.json")
    env.update(
        {
            "KB_IMPL_RESULT_PATH": str(implementation),
            "KB_REVIEW_RESULT_PATH": str(review),
            "FAKE_OPENCODE_REVIEW": "1",
            "KITTYBUILDER_REVIEW_MODELS": "rev-a rev-b",
            "KB_REVIEW_TIMEOUT_SECONDS": "2",
            "FAKE_OPENCODE_HANG_MODELS": "rev-a",
            "FAKE_OPENCODE_HANG_SECONDS": "3",
            "FAKE_OPENCODE_MODEL_LOG": str(model_log),
            "KB_REVIEW_CONTEXT_PATH": str(binding),
            "KB_REVIEW_SHA": subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=tmp_path, check=True,
                capture_output=True, text=True,
            ).stdout.strip(),
            "KB_REVIEW_DIFF_SHA256": "0" * 64,
        }
    )

    completed = subprocess.run(
        [str(REVIEWER)], cwd=tmp_path, env=env, capture_output=True, text=True, timeout=8
    )

    assert completed.returncode == 0, completed.stderr
    assert json.loads(review.read_text())["verdict"] == "approve"
    assert model_log.read_text() == "rev-b"
    assert "timed out" in completed.stderr
    assert "trying the next free model" in completed.stderr


def test_reviewer_defaults_to_free_model_and_writes_review_note(tmp_path: Path):
    """The free reviewer stays on a zero-cost model unless paid routing is explicit."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_git_repo(repo)
    bundle = tmp_path / "bundle.json"
    bundle.write_text('{"objective":"safe","packet_id":"pkt-1"}\n', encoding="utf-8")
    context = _manifest(bundle)
    implementation = tmp_path / "implementation.json"
    implementation.write_text('{"contract_version":1}\n', encoding="utf-8")
    review = tmp_path / "review.json"
    note = tmp_path / "review-note.md"
    model_log = tmp_path / "fake-model-used.txt"
    fake = _fake_opencode(tmp_path)
    binding = _review_binding(repo)
    env = _env(fake, bundle=bundle, context=context, result=tmp_path / "unused.json")
    env.update(
        {
            "KB_IMPL_RESULT_PATH": str(implementation),
            "KB_REVIEW_RESULT_PATH": str(review),
            "KB_REVIEW_NOTE_PATH": str(note),
            "FAKE_OPENCODE_REVIEW": "1",
            "FAKE_OPENCODE_MODEL_LOG": str(model_log),
            "KB_REVIEW_CONTEXT_PATH": str(binding),
            "KB_REVIEW_SHA": subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=repo, check=True,
                capture_output=True, text=True,
            ).stdout.strip(),
            "KB_REVIEW_DIFF_SHA256": "0" * 64,
        }
    )

    completed = subprocess.run(
        [str(REVIEWER)], cwd=repo, env=env, capture_output=True, text=True
    )

    assert completed.returncode == 0, completed.stderr
    assert model_log.read_text() == "opencode/nemotron-3-ultra-free"
    assert json.loads(review.read_text())["verdict"] == "approve"
    note_text = note.read_text()
    assert "# KittyBuilder review note" in note_text
    assert "Verdict: approve" in note_text
    assert "Reviewed commit:" in note_text


def test_worker_honours_explicit_paid_agent_without_changing_free_default(tmp_path: Path):
    repo = tmp_path / "repo-paid-worker"
    repo.mkdir()
    _init_git_repo(repo)
    bundle = tmp_path / "paid-worker-bundle.json"
    bundle.write_text('{"objective":"safe","packet_id":"pkt-paid"}\n', encoding="utf-8")
    context = _manifest(bundle)
    result = tmp_path / "paid-worker-result.json"
    fake = _fake_opencode(tmp_path)
    model_log = tmp_path / "paid-worker-model.txt"
    agent_log = tmp_path / "paid-worker-agent.txt"
    env = _env(fake, bundle=bundle, context=context, result=result)
    env.update(
        {
            "FAKE_OPENCODE_IMPLEMENT_CHANGE": "1",
            "FAKE_OPENCODE_MODEL_LOG": str(model_log),
            "FAKE_OPENCODE_AGENT_LOG": str(agent_log),
            "KITTYBUILDER_AGENT": "paid-builder",
            "KITTYBUILDER_MODEL": "openrouter/deepseek/deepseek-v4-flash",
        }
    )

    completed = subprocess.run(
        [str(WORKER)], cwd=repo, env=env, capture_output=True, text=True
    )

    assert completed.returncode == 0, completed.stderr
    assert agent_log.read_text() == "paid-builder"
    assert model_log.read_text() == "openrouter/deepseek/deepseek-v4-flash"


def test_reviewer_honours_explicit_paid_agent_and_model(tmp_path: Path):
    repo = tmp_path / "repo-paid-review"
    repo.mkdir()
    _init_git_repo(repo)
    bundle = tmp_path / "paid-review-bundle.json"
    bundle.write_text('{"objective":"safe","packet_id":"pkt-paid"}\n', encoding="utf-8")
    context = _manifest(bundle)
    implementation = tmp_path / "paid-review-implementation.json"
    implementation.write_text('{"contract_version":1}\n', encoding="utf-8")
    review = tmp_path / "paid-review.json"
    fake = _fake_opencode(tmp_path)
    binding = _review_binding(repo)
    model_log = tmp_path / "paid-review-model.txt"
    agent_log = tmp_path / "paid-review-agent.txt"
    env = _env(fake, bundle=bundle, context=context, result=tmp_path / "unused.json")
    env.update(
        {
            "KB_IMPL_RESULT_PATH": str(implementation),
            "KB_REVIEW_RESULT_PATH": str(review),
            "FAKE_OPENCODE_REVIEW": "1",
            "FAKE_OPENCODE_MODEL_LOG": str(model_log),
            "FAKE_OPENCODE_AGENT_LOG": str(agent_log),
            "KITTYBUILDER_REVIEW_AGENT": "paid-reviewer",
            "KITTYBUILDER_REVIEW_MODEL": "openrouter/qwen/qwen3.7-plus",
            "KB_REVIEW_CONTEXT_PATH": str(binding),
            "KB_REVIEW_SHA": subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=repo, check=True,
                capture_output=True, text=True,
            ).stdout.strip(),
            "KB_REVIEW_DIFF_SHA256": "0" * 64,
        }
    )

    completed = subprocess.run(
        [str(REVIEWER)], cwd=repo, env=env, capture_output=True, text=True
    )

    assert completed.returncode == 0, completed.stderr
    assert agent_log.read_text() == "paid-reviewer"
    assert model_log.read_text() == "openrouter/qwen/qwen3.7-plus"


def _wait_without_closing_stdin(proc: subprocess.Popen[str]) -> tuple[str, str]:
    try:
        # Generous budget: the adapter chain spawns several interpreters
        # before exiting. Only a worker that blocks on the still-open parent
        # stdin pipe should ever hit this timeout — that regression must stay
        # loud, but a fast machine should not be the pass/fail boundary.
        proc.wait(timeout=30)
    except subprocess.TimeoutExpired:
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=2)
        if proc.stdin is not None:
            proc.stdin.close()
        raise AssertionError("adapter waited for parent stdin EOF")
    if proc.stdin is not None:
        proc.stdin.close()
    stdout = proc.stdout.read() if proc.stdout is not None else ""
    stderr = proc.stderr.read() if proc.stderr is not None else ""
    return stdout, stderr


def test_worker_closes_stdin_before_launching_opencode(tmp_path: Path):
    repo = tmp_path / "stdin-worker"
    repo.mkdir()
    _init_git_repo(repo)
    bundle = tmp_path / "stdin-worker-bundle.json"
    bundle.write_text('{"objective":"safe","packet_id":"pkt-stdin"}\n')
    context = _manifest(bundle)
    result = tmp_path / "stdin-worker-result.json"
    fake = _fake_opencode(tmp_path)
    env = _env(fake, bundle=bundle, context=context, result=result)
    env.update({"FAKE_OPENCODE_READ_STDIN": "1"})
    proc = subprocess.Popen(
        [str(WORKER)], cwd=repo, env=env,
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True,
    )

    stdout, stderr = _wait_without_closing_stdin(proc)

    assert proc.returncode == 0, stderr
    assert json.loads(result.read_text())["status"] == "completed"
    assert "completed with" in stdout


def test_reviewer_closes_stdin_before_launching_opencode(tmp_path: Path):
    repo = tmp_path / "stdin-reviewer"
    repo.mkdir()
    _init_git_repo(repo)
    bundle = tmp_path / "stdin-review-bundle.json"
    bundle.write_text('{"objective":"safe","packet_id":"pkt-stdin"}\n')
    context = _manifest(bundle)
    implementation = tmp_path / "stdin-implementation.json"
    implementation.write_text('{"contract_version":1}\n')
    review = tmp_path / "stdin-review.json"
    fake = _fake_opencode(tmp_path)
    binding = _review_binding(repo)
    env = _env(fake, bundle=bundle, context=context, result=tmp_path / "unused.json")
    env.update({
        "KB_IMPL_RESULT_PATH": str(implementation),
        "KB_REVIEW_RESULT_PATH": str(review),
        "FAKE_OPENCODE_REVIEW": "1",
        "FAKE_OPENCODE_READ_STDIN": "1",
        "KB_REVIEW_CONTEXT_PATH": str(binding),
        "KB_REVIEW_SHA": subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=repo, check=True,
            capture_output=True, text=True,
        ).stdout.strip(),
        "KB_REVIEW_DIFF_SHA256": "0" * 64,
    })
    proc = subprocess.Popen(
        [str(REVIEWER)], cwd=repo, env=env,
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True,
    )

    _stdout, stderr = _wait_without_closing_stdin(proc)

    assert proc.returncode == 0, stderr
    assert json.loads(review.read_text())["verdict"] == "approve"
