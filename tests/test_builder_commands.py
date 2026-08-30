"""Tests for gateway.builder_commands — operator command dispatch."""

from __future__ import annotations

from pathlib import Path

import pytest

from gateway.builder_commands import (
    COMMAND_HANDLERS,
    CommandResult,
    command_result_payload,
    dispatch_operator_command,
)
from gateway.models.builder import BuilderCommandRequest


def test_command_handlers_registry_is_populated():
    assert len(COMMAND_HANDLERS) > 0
    assert "requeue" in COMMAND_HANDLERS
    assert "cancel" in COMMAND_HANDLERS
    assert "pause" in COMMAND_HANDLERS
    assert "resume" in COMMAND_HANDLERS
    assert "grant_attempt" in COMMAND_HANDLERS
    assert "run_validation" in COMMAND_HANDLERS
    assert "publish" in COMMAND_HANDLERS
    assert "recover_stale" in COMMAND_HANDLERS
    assert "reconcile_merges" in COMMAND_HANDLERS


def test_dispatch_unknown_action_returns_error():
    result = dispatch_operator_command(
        BuilderCommandRequest(action="nonexistent_action")
    )
    assert result.ok is False
    assert "unknown action" in result.error


def test_command_result_payload_serializes():
    result = CommandResult(ok=True, action="test", task_id="t1")
    payload = command_result_payload(result)
    assert payload["ok"] is True
    assert payload["action"] == "test"
    assert payload["task_id"] == "t1"


def test_command_result_payload_includes_available_actions():
    result = CommandResult(
        ok=False, action="bad", error="unknown", evidence={"available": ["a", "b"]}
    )
    payload = command_result_payload(result)
    assert payload["available"] == ["a", "b"]
