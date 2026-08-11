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

from gateway import action_queue, builder_commands
from gateway.models.builder import BuilderCommandRequest
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


def test_pause_delegates_to_the_canonical_command_dispatcher():
    received: BuilderCommandRequest | None = None

    def dispatch(request):
        nonlocal received
        received = request
        return builder_commands.CommandResult(
            ok=True, action="pause", detail="initiative demo-init paused"
        )

    with patch.object(builder_commands, "dispatch_operator_command", side_effect=dispatch):
        result = action_queue._exec_builder_pause(
            {"initiative_id": "demo-init", "reason": "because"}
        )
    assert received is not None
    assert received.action == "pause"
    assert received.initiative_id == "demo-init"
    assert received.reason == "because"
    assert result == "initiative demo-init paused"


def test_cancel_delegates_to_the_canonical_command_dispatcher():
    received: BuilderCommandRequest | None = None

    def dispatch(request):
        nonlocal received
        received = request
        return builder_commands.CommandResult(
            ok=True, action="cancel", task_id="kb_abc123", detail="task cancelled"
        )

    with patch.object(builder_commands, "dispatch_operator_command", side_effect=dispatch):
        action_queue._exec_builder_cancel({"packet_id": "kb_abc123"})
    assert received is not None
    assert received.action == "cancel"
    assert received.packet_id == "kb_abc123"


def test_legacy_action_route_uses_canonical_dispatch_for_requeue(monkeypatch):
    app = FastAPI()
    app.include_router(builder_control.router)
    received = {}

    def dispatch(request):
        received.update(request=request)
        return builder_commands.CommandResult(
            ok=True, action="requeue", task_id="packet-1", detail="requeued"
        )

    monkeypatch.setattr(builder_control, "dispatch_operator_command", dispatch)
    response = TestClient(app).post(
        "/builder/action",
        json={"action": "requeue", "packet_id": "packet-1", "reason": "retry"},
    )

    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert received["request"].action == "requeue"
    assert received["request"].packet_id == "packet-1"


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
