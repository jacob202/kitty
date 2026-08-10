from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from mcp.builder import operator

EXPECTED_ORDER = [
    "checkout",
    "runtime",
    "process",
    "transport",
    "contract",
    "context",
    "builder",
    "repository",
    "github",
    "provider",
]


def config_for(root: Path, port: int = 19876) -> operator.OperatorConfig:
    return operator.OperatorConfig(
        root=root,
        host="127.0.0.1",
        port=port,
        pid_file=root / "logs" / ".run" / "mcp.pid",
        log_file=root / "logs" / "mcp.log",
    )


@pytest.mark.asyncio
async def test_doctor_checkout_failure_blocks_dependent_boundaries(tmp_path: Path):
    config = config_for(tmp_path)

    report = await operator.doctor_report(config)

    assert [check["boundary"] for check in report["checks"]] == EXPECTED_ORDER
    assert report["first_failure"]["boundary"] == "checkout"
    assert report["checks"][0]["state"] == "fail"
    assert all(check["state"] == "blocked" for check in report["checks"][1:])
    assert isinstance(report["next_action"], str) and report["next_action"].strip()
    assert sum(bool(report["next_action"]) for _ in [0]) == 1


def test_github_unavailable_is_external_warning_unless_publication_required(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    config = config_for(tmp_path)
    monkeypatch.setattr(operator.shutil, "which", lambda name: None if name == "gh" else "/bin/true")

    optional = operator._check_github(config, publication_required=False)
    required = operator._check_github(config, publication_required=True)

    assert optional["state"] == "warn"
    assert optional["classification"] == "external"
    assert required["state"] == "fail"
    assert required["classification"] == "external"


def test_provider_unavailable_never_invokes_paid_fallback(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    config = config_for(tmp_path)
    monkeypatch.setattr(operator.shutil, "which", lambda _name: None)

    def forbidden_run(*_args, **_kwargs):
        raise AssertionError("provider readiness must not invoke a model/provider")

    monkeypatch.setattr(operator.subprocess, "run", forbidden_run)
    check = operator._check_provider(config)

    assert check["state"] == "warn"
    assert check["classification"] == "external"
    assert "free" in check["summary"].lower()


def test_stopped_status_has_exactly_one_action(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    config = config_for(tmp_path)
    monkeypatch.setattr(operator, "_listener_pids", lambda _port: [])

    report = operator.status_report(config)

    assert report["state"] == "stopped"
    assert report["next_action"] == "Run 'kitty mcp up'."
    assert report["process"]["state"] == "stopped"


@pytest.mark.asyncio
async def test_doctor_uses_readonly_evidence_and_never_execution_mutations(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    root = Path(__file__).parents[1]
    config = config_for(root)
    db_path = tmp_path / "builder.db"
    db_path.write_bytes(b"placeholder")

    monkeypatch.setattr(
        operator,
        "process_status",
        lambda _config: {
            "state": "running",
            "pid": 123,
            "alive": True,
            "owned": True,
            "listener_pids": [123],
            "command": "python -m mcp.builder.server",
            "cwd": str(root),
            "summary": "owned MCP process is running",
        },
    )

    async def fake_probe(_endpoint: str, *, call_context: bool = True):
        return {
            "initialized": True,
            "tools": sorted(operator.probe.EXPECTED_TOOLS),
            "context": {"ok": True, "operation": "kitty_context", "state": "ready"},
        }

    monkeypatch.setattr(operator.probe, "probe_protocol", fake_probe)
    monkeypatch.setattr(operator, "_builder_db_path", lambda: db_path)
    monkeypatch.setattr(operator.builder_status_readonly, "build_status_snapshot_readonly", lambda **_kw: {"queue": {"total": 0}, "initiatives": []})
    monkeypatch.setattr(operator, "_check_repository", lambda _config: operator._check("repository", "pass", "repository ready"))
    monkeypatch.setattr(operator, "_check_github", lambda _config, publication_required=False: operator._check("github", "warn", "GitHub external", classification="external"))
    monkeypatch.setattr(operator, "_check_provider", lambda _config: operator._check("provider", "warn", "free route unavailable", classification="external"))

    from mcp.builder import commands
    from gateway import builder_initiative, builder_queue

    def forbidden(*_args, **_kwargs):
        raise AssertionError("doctor called a mutating execution/storage function")

    for name in ("execution_start", "publication_prepare", "mission_approve"):
        monkeypatch.setattr(commands, name, forbidden)
    monkeypatch.setattr(builder_initiative, "init_db", forbidden)
    monkeypatch.setattr(builder_queue, "recover_expired_leases", forbidden)

    report = await operator.doctor_report(config)

    assert report["ok"] is True
    assert report["state"] == "degraded"
    assert report["first_failure"] is None
