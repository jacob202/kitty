"""Every Builder button must reach a real executor.

Regression guard: config/action_tiers.json carried T0 tiers for all five builder
kinds since 2026-07-02, but no executors were ever registered. /builder/action
returned HTTP 200 with {"ok": false} and the UI buttons silently did nothing.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from gateway import action_queue
from gateway.routes import builder_control

BUILDER_KINDS = [
    "builder.run_next",
    "builder.pause_initiative",
    "builder.resume_initiative",
    "builder.cancel_task",
    "builder.cleanup",
]


@pytest.mark.parametrize("kind", BUILDER_KINDS)
def test_builder_kind_has_an_executor(kind):
    """The bug was a tier with no executor — assert both halves exist."""
    assert kind in action_queue._EXECUTORS, f"{kind} has no executor registered"
    registry = action_queue._registry()
    assert kind in registry, f"{kind} is not in the built registry"


def test_pause_invokes_the_cli_with_the_initiative():
    with patch.object(action_queue, "_run_kitty", return_value="") as run:
        result = action_queue._exec_builder_pause(
            {"initiative_id": "demo-init", "reason": "because"}
        )
    args = run.call_args[0][0]
    assert args[:3] == ["initiative", "pause", "demo-init"]
    assert "because" in args
    assert "demo-init" in result


def test_cancel_invokes_operator_cancel_with_the_packet():
    with patch.object(action_queue, "_run_kitty", return_value="") as run:
        action_queue._exec_builder_cancel({"packet_id": "kb_abc123"})
    args = run.call_args[0][0]
    assert args[:3] == ["queue", "operator-cancel", "kb_abc123"]


def test_run_next_does_not_block_the_request():
    """A packet run takes minutes; the executor must hand off and return."""
    with patch.object(action_queue.subprocess, "Popen") as popen:
        result = action_queue._exec_builder_run_next({"initiative_id": "demo-init"})
    assert popen.called, "run_next must spawn the drain script"
    assert popen.call_args.kwargs.get("start_new_session") is True, (
        "must detach, or the run dies with the request"
    )
    assert "demo-init" in result


def test_run_kitty_fails_loud_on_nonzero_exit():
    """Non-negotiable #1: no silent failure. A bad exit must raise."""

    class _Proc:
        returncode = 2
        stdout = ""
        stderr = "boom"

    with patch.object(action_queue.subprocess, "run", return_value=_Proc()):
        with pytest.raises(RuntimeError, match="boom"):
            action_queue._run_kitty(["queue", "status"])


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(action_queue, "ACTIONS_DB_FILE", tmp_path / "kitty.db", raising=False)
    action_queue.reload_registry()
    app = FastAPI()
    app.include_router(builder_control.router)
    yield TestClient(app)
    action_queue.reload_registry()


def test_builder_action_reports_failure_when_the_executor_fails(client):
    """action_queue.execute() catches executor exceptions and records
    status='failed' instead of raising — /builder/action must propagate that
    record instead of assuming a returned (non-raising) execute() succeeded."""
    with patch.object(action_queue, "_run_kitty", side_effect=RuntimeError("boom")):
        r = client.post("/builder/action", json={"action": "resume", "initiative_id": "demo-init"})

    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False
    assert "boom" in body["error"]


def test_builder_action_reports_success_when_the_executor_succeeds(client):
    with patch.object(action_queue, "_run_kitty", return_value=""):
        r = client.post("/builder/action", json={"action": "resume", "initiative_id": "demo-init"})

    assert r.status_code == 200
    assert r.json()["ok"] is True
