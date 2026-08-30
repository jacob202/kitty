"""Tests for gateway.builder_commands — typed operator command functions."""

from gateway.builder_commands import (
    COMMAND_HANDLERS,
    CommandResult,
    command_cancel,
    command_pause,
    command_publish,
    command_reconcile_merges,
    command_recover_stale,
    command_requeue,
    command_resume,
    command_run_validation,
    dispatch_operator_command,
)
from gateway.models.builder import BuilderCommandRequest


class TestCommandResult:
    def test_ok_result(self):
        result = CommandResult(
            ok=True,
            action="cancel",
            task_id="abc",
            detail="done",
            event_id=1,
        )
        assert result.ok is True
        assert result.action == "cancel"
        assert result.task_id == "abc"
        assert result.detail == "done"
        assert result.error is None
        assert result.event_id == 1

    def test_error_result(self):
        result = CommandResult(
            ok=False,
            action="cancel",
            task_id="abc",
            error="not found",
        )
        assert result.ok is False
        assert result.error == "not found"
        assert result.detail is None

    def test_default_evidence_empty(self):
        result = CommandResult(ok=True, action="test")
        assert result.evidence == {}


class TestCommandHandlersRegistered:
    def test_all_handlers_registered(self):
        assert set(COMMAND_HANDLERS.keys()) == {
            "requeue",
            "cancel",
            "pause",
            "resume",
            "run_validation",
            "publish",
            "recover_stale",
            "reconcile_merges",
        }

    def test_each_handler_is_callable(self):
        for key, handler in COMMAND_HANDLERS.items():
            assert callable(handler), f"{key} handler must be callable"


class TestOperatorCommandDispatch:
    def test_packet_id_is_the_task_id_alias_for_legacy_ui_payloads(self, monkeypatch):
        received = {}

        def fake_cancel(task_id, *, actor, reason):
            received.update(task_id=task_id, actor=actor, reason=reason)
            return CommandResult(ok=True, action="cancel", task_id=task_id)

        monkeypatch.setitem(COMMAND_HANDLERS, "cancel", fake_cancel)
        result = dispatch_operator_command(
            BuilderCommandRequest(
                action="cancel",
                packet_id="packet-1",
                reason="stop it",
                actor="builder-ui",
            )
        )

        assert result.ok is True
        assert received == {
            "task_id": "packet-1",
            "actor": "builder-ui",
            "reason": "stop it",
        }

    def test_unknown_action_returns_available_commands(self):
        result = dispatch_operator_command(BuilderCommandRequest(action="not-a-command"))

        assert result.ok is False
        assert result.error == "unknown action: not-a-command"
        assert "cancel" in result.evidence["available"]


class TestRequeueMissingTask:
    def test_requeue_missing_task_returns_error(self):
        result = command_requeue("nonexistent-task-id-12345", actor="test")
        assert result.ok is False
        assert result.action == "requeue"
        assert result.error and "not found" in result.error


class TestCancelMissingTask:
    def test_cancel_missing_task_returns_error(self):
        result = command_cancel("nonexistent-task-id-12345", actor="test")
        assert result.ok is False
        assert result.action == "cancel"
        assert result.error and "not found" in result.error


class TestPauseMissingInitiative:
    def test_pause_missing_initiative_returns_error(self):
        result = command_pause("nonexistent-initiative-id-12345", actor="test")
        assert result.ok is False
        assert result.action == "pause"
        assert result.error and "not found" in result.error


class TestResumeMissingInitiative:
    def test_resume_missing_initiative_returns_error(self):
        result = command_resume("nonexistent-initiative-id-12345", actor="test")
        assert result.ok is False
        assert result.action == "resume"
        assert result.error and "not found" in result.error



class TestDirectPythonAuthorities:
    def test_publish_calls_publish_service_directly(self, monkeypatch):
        called = {}

        def fake_publish(task_id, *, remote="origin"):
            called.update(task_id=task_id, remote=remote)
            return {"task_id": task_id, "pr": {"pr_number": 42}}

        monkeypatch.setattr("gateway.builder_commands.publish_task", fake_publish)
        result = command_publish("task-1", actor="test")

        assert result.ok is True
        assert called == {"task_id": "task-1", "remote": "origin"}
        assert result.evidence["pr"]["pr_number"] == 42

    def test_recover_calls_queue_recovery_directly(self, monkeypatch):
        monkeypatch.setattr(
            "gateway.builder_commands.recover_durable_issues",
            lambda: {"total": 2, "claimed_requeued": 1, "running_blocked": 1},
        )
        result = command_recover_stale(actor="test")
        assert result.ok is True
        assert result.evidence["total"] == 2

    def test_reconcile_calls_merge_detector_directly(self, monkeypatch):
        monkeypatch.setattr(
            "gateway.builder_commands.detect_merged_prs",
            lambda: {"promoted": ["task-1"], "already_merged": [], "errors": []},
        )
        result = command_reconcile_merges(actor="test")
        assert result.ok is True
        assert result.evidence["promoted"] == ["task-1"]

    def test_validation_uses_open_attempt_and_canonical_validator(self, monkeypatch):
        calls = {}
        monkeypatch.setattr(
            "gateway.builder_commands.get_open_attempt_for_task",
            lambda task_id: {"id": 17, "task_id": task_id},
        )

        def fake_run_validation(attempt_id):
            calls["attempt_id"] = attempt_id
            return {
                "id": attempt_id,
                "validation": {
                    "status": "passed",
                    "commands": [{"command": "pytest", "passed": True}],
                },
            }

        monkeypatch.setattr("gateway.builder_commands.run_validation", fake_run_validation)
        result = command_run_validation("task-1", actor="test")

        assert result.ok is True
        assert calls == {"attempt_id": 17}
        assert result.evidence["status"] == "passed"

    def test_validation_rejects_skipped_validation(self, monkeypatch):
        monkeypatch.setattr(
            "gateway.builder_commands.get_open_attempt_for_task",
            lambda task_id: {"id": 18, "task_id": task_id},
        )
        monkeypatch.setattr(
            "gateway.builder_commands.run_validation",
            lambda attempt_id: {
                "id": attempt_id,
                "validation": {"status": "skipped", "commands": []},
            },
        )
        result = command_run_validation("task-1", actor="test")
        assert result.ok is False
        assert "validation commands" in result.error
