"""Contract tests for the free OpenCode KittyBuilder adapter scripts."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / "scripts" / "kittybuilder_opencode_worker.sh"
REVIEWER = ROOT / "scripts" / "kittybuilder_opencode_reviewer.sh"


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
        """#!/usr/bin/env python3
import json
import os
import re
import sys
from pathlib import Path

args = sys.argv
model = args[args.index("--model") + 1] if "--model" in args else ""
fail_models = set(
    filter(None, os.environ.get("FAKE_OPENCODE_FAIL_MODELS", "").split(","))
)
if model in fail_models:
    if os.environ.get("FAKE_OPENCODE_FAIL_MUTATE"):
        Path("partial-work.txt").write_text("partial\\n", encoding="utf-8")
    raise SystemExit(1)
prompt = args[-1]
match = re.search(r"[Ww]rite a JSON object to (.+?) with exactly", prompt)
if not match:
    raise SystemExit("prompt did not contain a contract output path")
output = Path(match.group(1))
if os.environ.get("FAKE_OPENCODE_MUTATE"):
    Path("reviewer-mutated.txt").write_text("mutation\\n", encoding="utf-8")
if os.environ.get("FAKE_OPENCODE_REVIEW"):
    payload = {"contract_version": 1, "verdict": "approve", "summary": "ok"}
else:
    payload = {"contract_version": 1, "status": "completed", "summary": "ok"}
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


def test_worker_stages_and_validates_local_context(tmp_path: Path):
    _init_git_repo(tmp_path)
    bundle = tmp_path / "bundle.json"
    bundle.write_text('{"objective":"safe"}\n', encoding="utf-8")
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


def test_worker_rejects_mismatched_context_before_opencode(tmp_path: Path):
    _init_git_repo(tmp_path)
    bundle = tmp_path / "bundle.json"
    bundle.write_text('{"objective":"safe"}\n', encoding="utf-8")
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
    bundle.write_text('{"objective":"safe"}\n', encoding="utf-8")
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
    bundle.write_text('{"objective":"safe"}\n', encoding="utf-8")
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
    bundle.write_text('{"objective":"safe"}\n', encoding="utf-8")
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


def test_worker_never_falls_back_over_partial_work(tmp_path: Path):
    _init_git_repo(tmp_path)
    bundle = tmp_path / "bundle.json"
    bundle.write_text('{"objective":"safe"}\n', encoding="utf-8")
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
    bundle.write_text('{"objective":"safe"}\n', encoding="utf-8")
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
    bundle.write_text('{"objective":"safe"}\n', encoding="utf-8")
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
    bundle.write_text('{"objective":"safe"}\n', encoding="utf-8")
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


def test_reviewer_falls_through_ladder_on_clean_model_failure(tmp_path: Path):
    _init_git_repo(tmp_path)
    bundle = tmp_path / "bundle.json"
    bundle.write_text('{"objective":"safe"}\n', encoding="utf-8")
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
    assert "Free review completed with rev-b" in completed.stdout
