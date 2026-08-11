from __future__ import annotations

from pathlib import Path

from scripts.agent_council import build_workers, run_council


def test_build_workers_use_read_only_controls(tmp_path: Path) -> None:
    workers = build_workers(tmp_path, "review this")
    commands = {worker.name: worker.command for worker in workers}
    claude = next(worker for worker in workers if worker.name == "Claude")

    assert {"Codex", "Claude", "OpenCode"} == set(commands)
    assert "--sandbox" in commands["Codex"]
    assert "read-only" in commands["Codex"]
    assert "--permission-mode" in commands["Claude"]
    assert "plan" in commands["Claude"]
    assert claude.fallback_command is not None
    assert "opencode/claude-sonnet-4" in claude.fallback_command
    assert claude.fallback_environment == {
        "OPENCODE_CONFIG_CONTENT": '{"permission": {"edit": "deny", "bash": "deny", "external_directory": "deny"}}'
    }
    assert workers[2].environment == {
        "OPENCODE_CONFIG_CONTENT": '{"permission": {"edit": "deny", "bash": "deny", "external_directory": "deny"}}'
    }


def test_dry_run_labels_every_worker(tmp_path: Path) -> None:
    result = run_council(tmp_path, "test wiring", timeout=1, dry_run=True)

    assert "## Codex" in result
    assert "## Claude" in result
    assert "## OpenCode" in result
    assert "test wiring" in result


def test_worker_failure_is_explicit(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("COUNCIL_CODEX_MODEL", "test-model")
    workers = build_workers(tmp_path, "test")
    codex = next(worker for worker in workers if worker.name == "Codex")

    from scripts import agent_council

    broken = agent_council.Worker(codex.name, ("/definitely/missing/codex",))
    assert "ERROR: executable unavailable" in agent_council.run_worker(
        broken, timeout=1, dry_run=False
    )


def test_worker_timeout_uses_visible_fallback(monkeypatch) -> None:
    from scripts import agent_council

    def fake_run(command, **kwargs):
        if command == ("primary",):
            raise agent_council.subprocess.TimeoutExpired(command, kwargs["timeout"])
        return agent_council.subprocess.CompletedProcess(
            command, 0, stdout="fallback ok", stderr=""
        )

    monkeypatch.setattr(agent_council.subprocess, "run", fake_run)
    worker = agent_council.Worker(
        "Claude",
        ("primary",),
        fallback_command=("fallback",),
        fallback_environment={"COUNCIL_TEST": "1"},
        fallback_label="fallback path",
    )

    result = agent_council.run_worker(worker, timeout=7, dry_run=False)

    assert "WARNING: primary worker failed; retrying via fallback path." in result
    assert "ERROR: timed out after 7s" in result
    assert "fallback ok" in result
