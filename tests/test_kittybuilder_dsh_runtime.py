from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts" / "kittybuilder_dsh_headless.mjs"
LAUNCHER = ROOT / "scripts" / "kittybuilder_dsh.sh"
WORKER = ROOT / "scripts" / "kittybuilder_dsh_worker.sh"
REVIEWER = ROOT / "scripts" / "kittybuilder_dsh_reviewer.sh"


def test_dsh_adapter_files_exist() -> None:
    for path in (RUNNER, LAUNCHER, WORKER, REVIEWER):
        assert path.is_file(), path


def test_headless_runner_mounts_requested_agent_preset() -> None:
    text = RUNNER.read_text(encoding="utf-8")
    assert '"agentPresets"' in text or "'agentPresets'" in text
    assert "presets.mount(agentCtx, presetId)" in text
    assert "agentPreset: presetId" in text


def test_headless_runner_defaults_reasoning_effort_for_router_models() -> None:
    text = RUNNER.read_text(encoding="utf-8")
    assert "KITTY_DSH_REASONING_EFFORT" in text
    assert "reasoningEffort" in text


def test_launcher_builds_headless_profile_with_preset_registry() -> None:
    text = LAUNCHER.read_text(encoding="utf-8")
    assert "@deepseek-ai/dsh-agent-presets" in text
    assert "headless-runner" in text and "disabled: true" in text
    assert "kitty-headless-runner" in text
    assert "KITTY_DSH_PRESET" in text
    assert "DSH_PERMISSION_MODE" in text


def test_launcher_passes_requested_route_and_preset_to_dsh(tmp_path: Path) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    log = tmp_path / "dsh.log"
    fake = fake_bin / "dsh"
    fake.write_text(
        "#!/bin/sh\n"
        "printf '%s\\n' \"$KITTY_DSH_PRESET|$KITTY_DSH_PROVIDER|$KITTY_DSH_MODEL|$DSH_PERMISSION_MODE\" > \"$FAKE_DSH_LOG\"\n"
        "printf '%s\\n' \"$@\" >> \"$FAKE_DSH_LOG\"\n"
        "printf 'OK\\n'\n",
        encoding="utf-8",
    )
    fake.chmod(0o755)
    task = tmp_path / "task.txt"
    task.write_text("do the thing", encoding="utf-8")
    env = dict(os.environ)
    env.update({"PATH": f"{fake_bin}:{env['PATH']}", "FAKE_DSH_LOG": str(log)})
    completed = subprocess.run(
        [
            "bash", str(LAUNCHER),
            "--preset", "kitty-forge",
            "--provider", "openrouter",
            "--model", "openrouter/deepseek/deepseek-v4-flash",
            "--permission", "workspace-write",
            "--task-file", str(task),
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert completed.returncode == 0, completed.stderr
    lines = log.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "kitty-forge|openrouter|deepseek/deepseek-v4-flash|workspace-write"
    assert "--profile" in lines and "headless" in lines
    assert "--patch" in lines
    assert "do the thing" in lines


def test_worker_and_reviewer_use_different_dsh_permissions_and_presets() -> None:
    worker = WORKER.read_text(encoding="utf-8")
    reviewer = REVIEWER.read_text(encoding="utf-8")
    assert "--preset kitty-forge" in worker
    assert "--permission workspace-write" in worker
    assert "--preset kitty-sprint" in reviewer
    assert "--permission read-only" in reviewer
    assert "opencode run" not in worker
    assert "opencode run" not in reviewer

def test_cli_no_longer_names_opencode_as_the_default_harness() -> None:
    cli = (ROOT / "gateway" / "builder_cli.py").read_text(encoding="utf-8")
    supervisor = (ROOT / "gateway" / "builder_supervisor.py").read_text(encoding="utf-8")
    assert "scripts/kittybuilder_dsh_worker.sh" in cli
    assert "scripts/kittybuilder_dsh_reviewer.sh" in cli
    assert 'worker = "dsh-free"' in cli
    assert 'worker = f"dsh-paid-{paid_route.tier}"' in cli
    assert "scripts/kittybuilder_dsh_worker.sh" in supervisor
    assert "scripts/kittybuilder_dsh_reviewer.sh" in supervisor


def _init_repo(path: Path) -> str:
    (path / "README.md").write_text("dsh adapter test\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "Adapter Test"], cwd=path, check=True)
    subprocess.run(["git", "add", "README.md"], cwd=path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=path, check=True)
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=path, check=True, capture_output=True, text=True
    ).stdout.strip()


def _bundle_and_manifest(path: Path, *, base_sha: str) -> tuple[Path, Path]:
    bundle = path / "bundle.json"
    bundle.write_text(json.dumps({"packet": "test"}), encoding="utf-8")
    digest = hashlib.sha256(bundle.read_bytes()).hexdigest()
    manifest = path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "manifest_version": 1,
                "task_id": "task-1",
                "attempt_id": 7,
                "bundle_sha256": digest,
                "lease": {"base_sha": base_sha},
                "context": {"task_bundle": {"sha256": digest}},
            }
        ),
        encoding="utf-8",
    )
    return bundle, manifest


def _fake_dsh_for_contracts(tmp_path: Path) -> tuple[Path, Path]:
    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    log = tmp_path / "fake-dsh-contract.log"
    log.touch()
    fake = fake_bin / "dsh"
    fake.write_text(
        f"#!{sys.executable}\n"
        "import json, os, re, sys\n"
        "from pathlib import Path\n"
        "task = sys.argv[-1]\n"
        "with Path(os.environ['FAKE_DSH_CONTRACT_LOG']).open('a', encoding='utf-8') as fh:\n"
        "    fh.write('|'.join([os.environ.get('KITTY_DSH_PRESET',''), os.environ.get('KITTY_DSH_PROVIDER',''), os.environ.get('KITTY_DSH_MODEL',''), os.environ.get('DSH_PERMISSION_MODE','')]) + '\\n')\n"
        "if 'FINAL RESPONSE exactly one JSON object' in task:\n"
        "    print(json.dumps({'contract_version':1,'verdict':'approve','summary':'ok','findings':[]}))\n"
        "else:\n"
        "    m = re.search(r'write a JSON object to (.+?) with exactly', task, re.I | re.S)\n"
        "    if not m: raise SystemExit('worker prompt missing result path')\n"
        "    Path(m.group(1).strip()).write_text(json.dumps({'contract_version':1,'status':'completed','summary':'ok','diff_summary':'none','claims':[]}), encoding='utf-8')\n"
        "    print('done')\n",
        encoding="utf-8",
    )
    fake.chmod(0o755)
    return fake_bin, log


def test_dsh_worker_preserves_builder_result_contract(tmp_path: Path) -> None:
    head = _init_repo(tmp_path)
    bundle, manifest = _bundle_and_manifest(tmp_path, base_sha=head)
    result = tmp_path / "runner-result.json"
    fake_bin, log = _fake_dsh_for_contracts(tmp_path)
    env = dict(os.environ)
    env.update(
        {
            "PATH": f"{fake_bin}:{env['PATH']}",
            "FAKE_DSH_CONTRACT_LOG": str(log),
            "KB_BUNDLE_PATH": str(bundle),
            "KB_CONTEXT_MANIFEST_PATH": str(manifest),
            "KB_RESULT_PATH": str(result),
            "KB_ATTEMPT_ID": "7",
            "KB_TASK_ID": "task-1",
            "KITTYBUILDER_AGENT": "paid-builder",
            "KITTYBUILDER_MODEL": "openrouter/deepseek/deepseek-v4-flash",
        }
    )
    completed = subprocess.run(
        ["bash", str(WORKER)], cwd=tmp_path, env=env, capture_output=True, text=True, timeout=15
    )
    assert completed.returncode == 0, completed.stderr
    assert json.loads(result.read_text(encoding="utf-8"))["status"] == "completed"
    assert log.read_text(encoding="utf-8").splitlines() == [
        "kitty-forge|openrouter|deepseek/deepseek-v4-flash|workspace-write"
    ]


def test_dsh_reviewer_is_read_only_and_handoffs_valid_json(tmp_path: Path) -> None:
    head = _init_repo(tmp_path)
    bundle, manifest = _bundle_and_manifest(tmp_path, base_sha=head)
    impl = tmp_path / "impl.json"
    impl.write_text(json.dumps({"contract_version": 1, "status": "completed"}), encoding="utf-8")
    review_binding = tmp_path / "review-binding.json"
    review_binding.write_text(
        json.dumps(
            {
                "task_id": "task-1",
                "attempt_id": 7,
                "review_sha": head,
                "diff_sha256": "0" * 64,
                "changed_paths": [],
            }
        ),
        encoding="utf-8",
    )
    result = tmp_path / "review-result.json"
    result.touch()
    fake_bin, log = _fake_dsh_for_contracts(tmp_path)
    env = dict(os.environ)
    env.update(
        {
            "PATH": f"{fake_bin}:{env['PATH']}",
            "FAKE_DSH_CONTRACT_LOG": str(log),
            "KB_BUNDLE_PATH": str(bundle),
            "KB_IMPL_RESULT_PATH": str(impl),
            "KB_REVIEW_RESULT_PATH": str(result),
            "KB_CONTEXT_MANIFEST_PATH": str(manifest),
            "KB_REVIEW_CONTEXT_PATH": str(review_binding),
            "KB_REVIEW_SHA": head,
            "KB_REVIEW_DIFF_SHA256": "0" * 64,
            "KB_ATTEMPT_ID": "7",
            "KB_TASK_ID": "task-1",
            "KITTYBUILDER_REVIEW_AGENT": "paid-reviewer",
            "KITTYBUILDER_REVIEW_MODEL": "openrouter/minimax/minimax-m3",
        }
    )
    before = subprocess.run(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"],
        cwd=tmp_path, check=True, capture_output=True, text=True,
    ).stdout
    completed = subprocess.run(
        ["bash", str(REVIEWER)], cwd=tmp_path, env=env, capture_output=True, text=True, timeout=15
    )
    assert completed.returncode == 0, completed.stderr
    review = json.loads(result.read_text(encoding="utf-8"))
    assert review["verdict"] == "approve"
    after = subprocess.run(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"],
        cwd=tmp_path, check=True, capture_output=True, text=True,
    ).stdout
    assert before == after
    assert log.read_text(encoding="utf-8").splitlines() == [
        "kitty-sprint|openrouter|minimax/minimax-m3|read-only"
    ]


def test_launcher_loads_openrouter_key_from_explicit_trusted_env_root(tmp_path: Path) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    log = tmp_path / "dsh-env.log"
    fake = fake_bin / "dsh"
    fake.write_text(
        "#!/bin/sh\n"
        'if [ -n "${OPENROUTER_API_KEY:-}" ]; then echo key_present > "$FAKE_DSH_LOG"; else echo key_missing > "$FAKE_DSH_LOG"; fi\n'
        "printf 'OK\n'\n",
        encoding="utf-8",
    )
    fake.chmod(0o755)
    task = tmp_path / "task.txt"
    task.write_text("ready", encoding="utf-8")
    (tmp_path / ".env").write_text("OPENROUTER_API_KEY=test-only-secret\n", encoding="utf-8")
    env = dict(os.environ)
    env.pop("OPENROUTER_API_KEY", None)
    env.update({
        "PATH": f"{fake_bin}:{env['PATH']}",
        "FAKE_DSH_LOG": str(log),
        "KITTY_BUILDER_REPO_ROOT": str(tmp_path),
    })
    completed = subprocess.run(
        [
            "bash", str(LAUNCHER), "--preset", "kitty-forge", "--provider", "openrouter",
            "--model", "openrouter/free", "--permission", "workspace-write", "--task-file", str(task),
        ],
        cwd=tmp_path, env=env, capture_output=True, text=True, timeout=10,
    )
    assert completed.returncode == 0, completed.stderr
    assert log.read_text(encoding="utf-8").strip() == "key_present"
    assert "test-only-secret" not in completed.stdout
    assert "test-only-secret" not in completed.stderr


def test_launcher_imports_only_openrouter_key_from_repo_env(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / "gateway" / "lib").mkdir(parents=True)
    (repo / "scripts").mkdir()
    # Use this checkout's launcher/runner/preset while pointing the credential root at an isolated env.
    env_root = tmp_path / "env-root"
    env_root.mkdir()
    (env_root / ".env").write_text(
        "OPENROUTER_API_KEY=test-openrouter-key\nGITHUB_TOKEN=must-not-propagate\nOTHER_SECRET=must-not-propagate\n",
        encoding="utf-8",
    )
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    log = tmp_path / "env.log"
    fake = fake_bin / "dsh"
    fake.write_text(
        "#!/bin/sh\n"
        "printf '%s|%s|%s\\n' \"${OPENROUTER_API_KEY:-}\" \"${GITHUB_TOKEN:-}\" \"${OTHER_SECRET:-}\" > \"$FAKE_DSH_ENV_LOG\"\n"
        "printf 'OK\\n'\n",
        encoding="utf-8",
    )
    fake.chmod(0o755)
    task = tmp_path / "task.txt"
    task.write_text("credential isolation", encoding="utf-8")
    env = dict(os.environ)
    env.pop("OPENROUTER_API_KEY", None)
    env.pop("GITHUB_TOKEN", None)
    env.pop("OTHER_SECRET", None)
    env.update({
        "PATH": f"{fake_bin}:{env['PATH']}",
        "FAKE_DSH_ENV_LOG": str(log),
        "KITTY_BUILDER_REPO_ROOT": str(env_root),
    })

    completed = subprocess.run(
        [
            "bash", str(LAUNCHER), "--preset", "kitty-forge", "--provider", "openrouter",
            "--model", "openrouter/free", "--permission", "workspace-write", "--task-file", str(task),
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert completed.returncode == 0, completed.stderr
    assert log.read_text(encoding="utf-8").strip() == "test-openrouter-key||"
