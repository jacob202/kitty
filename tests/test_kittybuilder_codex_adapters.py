from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADAPTER = ROOT / "scripts" / "kittybuilder_codex_adapter.py"


def _init_git_repo(root: Path) -> str:
    (root / "AGENTS.md").write_text("Stay within the packet scope.\n", encoding="utf-8")
    (root / "README.md").write_text("adapter test\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "Adapter Test"], cwd=root, check=True)
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=root, check=True)
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()


def _bundle(root: Path) -> Path:
    path = root.parent / f"{root.name}-bundle.json"
    path.write_text(json.dumps({"packet_id": "P1", "objective": "make the bounded change"}), encoding="utf-8")
    return path


def _manifest(bundle: Path) -> Path:
    digest = hashlib.sha256(bundle.read_bytes()).hexdigest()
    path = bundle.parent / f"{bundle.stem}-manifest.json"
    path.write_text(
        json.dumps({
            "manifest_version": 1,
            "task_id": "task-1",
            "attempt_id": 7,
            "bundle_sha256": digest,
            "context": {"task_bundle": {"sha256": digest}},
        }),
        encoding="utf-8",
    )
    return path


def _review_binding(root: Path, head: str) -> Path:
    path = root.parent / f"{root.name}-review-binding.json"
    path.write_text(
        json.dumps({
            "task_id": "task-1",
            "attempt_id": 7,
            "review_sha": head,
            "diff_sha256": "0" * 64,
            "changed_paths": ["implemented.txt"],
        }),
        encoding="utf-8",
    )
    return path


def _fake_codex(root: Path) -> Path:
    fake_dir = root.parent / f"{root.name}-bin"
    fake_dir.mkdir()
    fake = fake_dir / "codex"
    fake.write_text(
        f"#!{sys.executable}\n"
        + r'''import json
import os
import sys
import time
from pathlib import Path

args = sys.argv[1:]
log = os.environ.get("FAKE_CODEX_ARGS_LOG")
if log:
    Path(log).write_text(json.dumps(args), encoding="utf-8")
if os.environ.get("FAKE_CODEX_SLEEP"):
    time.sleep(float(os.environ["FAKE_CODEX_SLEEP"]))
if os.environ.get("FAKE_CODEX_MUTATE"):
    Path("reviewer-mutated.txt").write_text("bad\\n", encoding="utf-8")
if os.environ.get("FAKE_CODEX_IMPLEMENT_CHANGE"):
    Path("implemented.txt").write_text("real change\\n", encoding="utf-8")
if os.environ.get("FAKE_CODEX_EXIT"):
    raise SystemExit(int(os.environ["FAKE_CODEX_EXIT"]))
out = Path(args[args.index("-o") + 1])
if os.environ.get("FAKE_CODEX_REVIEW"):
    payload = {"contract_version": 1, "verdict": "approve", "summary": "review ok", "findings": []}
else:
    payload = {
        "contract_version": 1,
        "status": "completed",
        "summary": "implemented",
        "diff_summary": "one bounded file",
        "validation": {"passed": True, "output": "focused test passed"},
        "claims": ["bounded change complete"],
    }
out.write_text(json.dumps(payload), encoding="utf-8")
''',
        encoding="utf-8",
    )
    fake.chmod(0o755)
    return fake


def _base_env(root: Path, fake: Path, bundle: Path, manifest: Path) -> dict[str, str]:
    env = dict(os.environ)
    env.update({
        "PATH": f"{fake.parent}:{env['PATH']}",
        "KB_TASK_ID": "task-1",
        "KB_ATTEMPT_ID": "7",
        "KB_BUNDLE_PATH": str(bundle),
        "KB_CONTEXT_MANIFEST_PATH": str(manifest),
        "KB_WORKER_TIMEOUT_SECONDS": "5",
        "KB_REVIEW_TIMEOUT_SECONDS": "5",
    })
    return env


def test_codex_worker_uses_workspace_sandbox_writes_contract_and_commits(tmp_path: Path):
    _init_git_repo(tmp_path)
    bundle = _bundle(tmp_path)
    manifest = _manifest(bundle)
    fake = _fake_codex(tmp_path)
    result = tmp_path.parent / f"{tmp_path.name}-implementation.json"
    args_log = tmp_path.parent / f"{tmp_path.name}-worker-args.json"
    env = _base_env(tmp_path, fake, bundle, manifest)
    env.update({"KB_RESULT_PATH": str(result), "FAKE_CODEX_IMPLEMENT_CHANGE": "1", "FAKE_CODEX_ARGS_LOG": str(args_log)})

    completed = subprocess.run([sys.executable, str(ADAPTER), "worker"], cwd=tmp_path, env=env, capture_output=True, text=True, timeout=10)

    assert completed.returncode == 0, completed.stderr
    assert json.loads(result.read_text())["status"] == "completed"
    args = json.loads(args_log.read_text())
    assert args[:1] == ["exec"]
    assert "--ephemeral" in args
    assert args[args.index("--sandbox") + 1] == "workspace-write"
    assert "--output-schema" in args and "-o" in args
    subject = subprocess.run(["git", "log", "-1", "--format=%s"], cwd=tmp_path, check=True, capture_output=True, text=True).stdout.strip()
    assert subject.startswith("[P1] kittybuilder:")
    assert subprocess.run(["git", "status", "--porcelain"], cwd=tmp_path, check=True, capture_output=True, text=True).stdout == ""


def test_codex_worker_clean_timeout_is_provider_unavailable(tmp_path: Path):
    _init_git_repo(tmp_path)
    bundle = _bundle(tmp_path)
    manifest = _manifest(bundle)
    fake = _fake_codex(tmp_path)
    result = tmp_path.parent / f"{tmp_path.name}-implementation.json"
    env = _base_env(tmp_path, fake, bundle, manifest)
    env.update({"KB_RESULT_PATH": str(result), "KB_WORKER_TIMEOUT_SECONDS": "1", "FAKE_CODEX_SLEEP": "3"})

    completed = subprocess.run([sys.executable, str(ADAPTER), "worker"], cwd=tmp_path, env=env, capture_output=True, text=True, timeout=6)

    assert completed.returncode == 75
    assert not result.exists()
    assert "timed out" in completed.stderr.lower()
    assert subprocess.run(["git", "status", "--porcelain"], cwd=tmp_path, check=True, capture_output=True, text=True).stdout == ""


def test_codex_reviewer_is_read_only_and_writes_review_contract(tmp_path: Path):
    head = _init_git_repo(tmp_path)
    bundle = _bundle(tmp_path)
    manifest = _manifest(bundle)
    fake = _fake_codex(tmp_path)
    impl = tmp_path.parent / f"{tmp_path.name}-impl.json"
    impl.write_text('{"contract_version":1,"status":"completed"}\n', encoding="utf-8")
    binding = _review_binding(tmp_path, head)
    review = tmp_path.parent / f"{tmp_path.name}-review.json"
    note = tmp_path.parent / f"{tmp_path.name}-review.md"
    args_log = tmp_path.parent / f"{tmp_path.name}-review-args.json"
    env = _base_env(tmp_path, fake, bundle, manifest)
    env.update({
        "KB_IMPL_RESULT_PATH": str(impl),
        "KB_REVIEW_RESULT_PATH": str(review),
        "KB_REVIEW_NOTE_PATH": str(note),
        "KB_REVIEW_CONTEXT_PATH": str(binding),
        "KB_REVIEW_SHA": head,
        "KB_REVIEW_DIFF_SHA256": "0" * 64,
        "FAKE_CODEX_REVIEW": "1",
        "FAKE_CODEX_ARGS_LOG": str(args_log),
    })

    completed = subprocess.run([sys.executable, str(ADAPTER), "reviewer"], cwd=tmp_path, env=env, capture_output=True, text=True, timeout=10)

    assert completed.returncode == 0, completed.stderr
    assert json.loads(review.read_text())["verdict"] == "approve"
    assert "review ok" in note.read_text()
    args = json.loads(args_log.read_text())
    assert args[args.index("--sandbox") + 1] == "read-only"
    assert subprocess.run(["git", "status", "--porcelain"], cwd=tmp_path, check=True, capture_output=True, text=True).stdout == ""


def test_codex_reviewer_rejects_any_worktree_mutation(tmp_path: Path):
    head = _init_git_repo(tmp_path)
    bundle = _bundle(tmp_path)
    manifest = _manifest(bundle)
    fake = _fake_codex(tmp_path)
    impl = tmp_path.parent / f"{tmp_path.name}-impl.json"
    impl.write_text('{"contract_version":1,"status":"completed"}\n', encoding="utf-8")
    binding = _review_binding(tmp_path, head)
    review = tmp_path.parent / f"{tmp_path.name}-review.json"
    env = _base_env(tmp_path, fake, bundle, manifest)
    env.update({
        "KB_IMPL_RESULT_PATH": str(impl),
        "KB_REVIEW_RESULT_PATH": str(review),
        "KB_REVIEW_CONTEXT_PATH": str(binding),
        "KB_REVIEW_SHA": head,
        "KB_REVIEW_DIFF_SHA256": "0" * 64,
        "FAKE_CODEX_REVIEW": "1",
        "FAKE_CODEX_MUTATE": "1",
    })

    completed = subprocess.run([sys.executable, str(ADAPTER), "reviewer"], cwd=tmp_path, env=env, capture_output=True, text=True, timeout=10)

    assert completed.returncode != 0
    assert "changed the worktree" in completed.stderr


def test_codex_worker_invalid_context_leaves_no_staging_files(tmp_path: Path):
    _init_git_repo(tmp_path)
    bundle = _bundle(tmp_path)
    manifest = _manifest(bundle)
    data = json.loads(manifest.read_text())
    data["task_id"] = "wrong-task"
    manifest.write_text(json.dumps(data), encoding="utf-8")
    fake = _fake_codex(tmp_path)
    result = tmp_path.parent / f"{tmp_path.name}-invalid-context-result.json"
    env = _base_env(tmp_path, fake, bundle, manifest)
    env["KB_RESULT_PATH"] = str(result)

    completed = subprocess.run(
        [sys.executable, str(ADAPTER), "worker"],
        cwd=tmp_path, env=env, capture_output=True, text=True, timeout=10,
    )

    assert completed.returncode != 0
    assert not list(tmp_path.glob(".kittybuilder-codex-*"))
    assert subprocess.run(
        ["git", "status", "--porcelain"], cwd=tmp_path, check=True,
        capture_output=True, text=True,
    ).stdout == ""
