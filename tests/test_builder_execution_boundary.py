from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import threading
from pathlib import Path

import pytest

from gateway import builder_execution_boundary as boundary


def _serve_once(listener: socket.socket) -> None:
    try:
        conn, _ = listener.accept()
        conn.close()
    except OSError:
        pass


@pytest.mark.skipif(sys.platform != "darwin", reason="Seatbelt proof is macOS-specific")
def test_sandboxed_git_can_read_linked_worktree_metadata(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True)
    (repo / "README.md").write_text("hello\n")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=repo, check=True)

    worktree = tmp_path / "linked"
    subprocess.run(["git", "worktree", "add", "-q", "-b", "builder/test", str(worktree), "main"], cwd=repo, check=True)
    run_dir = tmp_path / "run"
    env = boundary.build_child_environment(dict(os.environ), run_dir=run_dir)
    raw_command = ["/bin/bash", "-lc", "git rev-parse --show-toplevel && git rev-parse HEAD && git status --porcelain"]
    profile = boundary.build_sandbox_profile(
        worktree=worktree,
        run_dir=run_dir,
        command=raw_command,
        environment=env,
    )
    common_git = repo / ".git"
    assert f'(allow file-read-metadata (literal "{common_git}"))' in profile
    assert f'(allow file-read-metadata (literal "{common_git / "worktrees"}"))' in profile

    command = boundary.wrap_command(
        raw_command,
        worktree=worktree,
        run_dir=run_dir,
        environment=env,
    )

    completed = subprocess.run(command, cwd=worktree, env=env, capture_output=True, text=True)

    assert completed.returncode == 0, completed.stderr
    lines = completed.stdout.splitlines()
    assert lines[0] == str(worktree)
    assert len(lines[1]) == 40


@pytest.mark.skipif(sys.platform != "darwin", reason="Seatbelt proof is macOS-specific")
def test_sandboxed_process_can_signal_same_sandbox_child_group(tmp_path: Path) -> None:
    worktree = tmp_path / "worktree"
    run_dir = tmp_path / "run"
    worktree.mkdir()
    run_dir.mkdir()
    env = boundary.build_child_environment(dict(os.environ), run_dir=run_dir)
    script = """
import os, signal, subprocess
proc = subprocess.Popen(['/bin/sleep', '2'], start_new_session=True)
try:
    os.killpg(proc.pid, signal.SIGTERM)
    proc.wait(timeout=1)
finally:
    if proc.poll() is None:
        proc.kill()
        proc.wait()
"""
    command = boundary.wrap_command(
        [str(Path(sys.executable).resolve()), "-c", script],
        worktree=worktree,
        run_dir=run_dir,
        environment=env,
    )

    completed = subprocess.run(command, cwd=worktree, env=env, capture_output=True, text=True)

    assert completed.returncode == 0, completed.stderr


def test_child_environment_is_explicit_and_secret_free(tmp_path: Path) -> None:
    source = dict(os.environ)
    source.update({"GATEWAY_SECRET": "sentinel", "OPENROUTER_API_KEY": "sentinel"})
    run_dir = tmp_path / "run"
    env = boundary.build_child_environment(source, run_dir=run_dir)

    assert "GATEWAY_SECRET" not in env
    assert "OPENROUTER_API_KEY" not in env
    assert env["HOME"].startswith(str(run_dir))
    assert env["TMPDIR"].startswith(str(run_dir))
    assert str(Path.home()) != env["HOME"]


@pytest.mark.skipif(sys.platform != "darwin", reason="Seatbelt proof is macOS-specific")
def test_real_child_cannot_escape_or_reach_loopback(tmp_path: Path) -> None:
    worktree = tmp_path / "worktree"
    run_dir = tmp_path / "run"
    worktree.mkdir()
    run_dir.mkdir()
    outside = tmp_path / "outside.txt"

    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    listener.settimeout(2)
    port = listener.getsockname()[1]
    thread = threading.Thread(target=_serve_once, args=(listener,), daemon=True)
    thread.start()

    result_path = run_dir / "result.json"
    script = """
import json, os, pathlib, socket
outside = pathlib.Path(os.environ['TEST_OUTSIDE'])
write_blocked = False
try:
    outside.write_text('escape')
except OSError:
    write_blocked = True
loopback_blocked = False
try:
    socket.create_connection(('127.0.0.1', int(os.environ['TEST_PORT'])), timeout=1).close()
except OSError:
    loopback_blocked = True
pathlib.Path(os.environ['TEST_RESULT']).write_text(json.dumps({
    'gateway_secret': os.environ.get('GATEWAY_SECRET'),
    'provider_secret': os.environ.get('OPENROUTER_API_KEY'),
    'write_blocked': write_blocked,
    'loopback_blocked': loopback_blocked,
}))
"""
    source = dict(os.environ)
    source.update({
        "GATEWAY_SECRET": "sentinel-gateway",
        "OPENROUTER_API_KEY": "sentinel-provider",
    })
    env = boundary.build_child_environment(source, run_dir=run_dir)
    env.update({
        "TEST_OUTSIDE": str(outside),
        "TEST_PORT": str(port),
        "TEST_RESULT": str(result_path),
    })
    command = boundary.wrap_command(
        [str(Path(sys.executable).resolve()), "-c", script],
        worktree=worktree,
        run_dir=run_dir,
        environment=env,
    )
    completed = subprocess.run(command, cwd=worktree, env=env, capture_output=True, text=True)
    listener.close()
    thread.join(timeout=2)

    assert completed.returncode == 0, completed.stderr
    result = json.loads(result_path.read_text())
    assert result == {
        "gateway_secret": None,
        "provider_secret": None,
        "write_blocked": True,
        "loopback_blocked": True,
    }
    assert not outside.exists()


@pytest.mark.skipif(sys.platform != "darwin", reason="Seatbelt proof is macOS-specific")
def test_run_worker_enforces_real_child_boundary(tmp_path: Path, monkeypatch) -> None:
    from gateway import builder_queue as bq
    from gateway import builder_runner as br

    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True)
    (repo / "README.md").write_text("hello\n")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=repo, check=True)

    db_path = tmp_path / "queue" / "builder_queue.db"
    bq.init_db(db_path)
    task = bq.create_task(
        "boundary integration",
        repo_path=str(repo),
        allowed_paths=["boundary.json"],
        db_path=db_path,
    )
    outside = tmp_path / "outside.txt"
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    listener.settimeout(2)
    port = listener.getsockname()[1]
    thread = threading.Thread(target=_serve_once, args=(listener,), daemon=True)
    thread.start()

    monkeypatch.setenv("GATEWAY_SECRET", "sentinel-gateway")
    monkeypatch.setenv("OPENROUTER_API_KEY", "sentinel-provider")
    script = """
import json, os, pathlib, socket
outside = pathlib.Path(os.environ['TEST_OUTSIDE'])
write_blocked = False
try:
    outside.write_text('escape')
except OSError:
    write_blocked = True
loopback_blocked = False
try:
    socket.create_connection(('127.0.0.1', int(os.environ['TEST_PORT'])), timeout=1).close()
except OSError:
    loopback_blocked = True
pathlib.Path('boundary.json').write_text(json.dumps({
    'gateway_secret': os.environ.get('GATEWAY_SECRET'),
    'provider_secret': os.environ.get('OPENROUTER_API_KEY'),
    'write_blocked': write_blocked,
    'loopback_blocked': loopback_blocked,
}))
"""
    run = br.run_worker(
        task["id"],
        [str(Path(sys.executable).resolve()), "-c", script],
        repo_root=repo,
        db_path=db_path,
        extra_env={"TEST_OUTSIDE": str(outside), "TEST_PORT": str(port)},
    )
    listener.close()
    thread.join(timeout=2)

    report = run["final_report"] or {}
    worktree = Path(report["worktree"])
    result = json.loads((worktree / "boundary.json").read_text())
    assert result == {
        "gateway_secret": None,
        "provider_secret": None,
        "write_blocked": True,
        "loopback_blocked": True,
    }
    assert not outside.exists()


@pytest.mark.skipif(sys.platform != "darwin", reason="Seatbelt proof is macOS-specific")
def test_review_command_is_read_only_secret_free_and_loopback_denied(
    tmp_path: Path, monkeypatch
) -> None:
    from gateway import builder_loop as bl

    worktree = tmp_path / "worktree"
    review_dir = tmp_path / "review"
    worktree.mkdir()
    review_dir.mkdir()
    outside = tmp_path / "outside.txt"
    worktree_write = worktree / "reviewer-write.txt"
    result_path = review_dir / "review.json"

    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    listener.settimeout(2)
    port = listener.getsockname()[1]
    thread = threading.Thread(target=_serve_once, args=(listener,), daemon=True)
    thread.start()

    monkeypatch.setenv("GATEWAY_SECRET", "sentinel-gateway")
    monkeypatch.setenv("OPENROUTER_API_KEY", "sentinel-provider")
    script = """
import json, os, pathlib, socket
worktree_write = pathlib.Path(os.environ['TEST_WORKTREE_WRITE'])
outside = pathlib.Path(os.environ['TEST_OUTSIDE'])
def blocked_write(path):
    try:
        path.write_text('escape')
        return False
    except OSError:
        return True
loopback_blocked = False
try:
    socket.create_connection(('127.0.0.1', int(os.environ['TEST_PORT'])), timeout=1).close()
except OSError:
    loopback_blocked = True
pathlib.Path(os.environ['KB_REVIEW_RESULT_PATH']).write_text(json.dumps({
    'gateway_secret': os.environ.get('GATEWAY_SECRET'),
    'provider_secret': os.environ.get('OPENROUTER_API_KEY'),
    'worktree_write_blocked': blocked_write(worktree_write),
    'outside_write_blocked': blocked_write(outside),
    'loopback_blocked': loopback_blocked,
}))
"""
    error = bl._run_review_command(
        [str(Path(sys.executable).resolve()), "-c", script],
        cwd=worktree,
        env_extra={
            "TEST_WORKTREE_WRITE": str(worktree_write),
            "TEST_OUTSIDE": str(outside),
            "TEST_PORT": str(port),
            "KB_REVIEW_RESULT_PATH": str(result_path),
        },
        timeout_seconds=5,
    )
    listener.close()
    thread.join(timeout=2)

    assert error is None
    result = json.loads(result_path.read_text())
    assert result == {
        "gateway_secret": None,
        "provider_secret": None,
        "worktree_write_blocked": True,
        "outside_write_blocked": True,
        "loopback_blocked": True,
    }
    assert not worktree_write.exists()
    assert not outside.exists()
