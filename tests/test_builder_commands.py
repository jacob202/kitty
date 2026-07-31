"""Tests for gateway.builder_commands — typed operator command functions."""


from gateway.builder_commands import (
    COMMAND_HANDLERS,
    CommandResult,
    OperatorCommandError,
    command_cancel,
    command_pause,
    command_requeue,
    command_resume,
)


class TestCommandResult:
    def test_ok_result(self):
        r = CommandResult(ok=True, action="cancel", task_id="abc", detail="done", event_id=1)
        assert r.ok is True
        assert r.action == "cancel"
        assert r.task_id == "abc"
        assert r.detail == "done"
        assert r.error is None
        assert r.event_id == 1

    def test_error_result(self):
        r = CommandResult(ok=False, action="cancel", task_id="abc", error="not found")
        assert r.ok is False
        assert r.error == "not found"
        assert r.detail is None

    def test_default_evidence_empty(self):
        r = CommandResult(ok=True, action="test")
        assert r.evidence == {}


class TestCommandHandlersRegistered:
    def test_all_handlers_registered(self):
        assert set(COMMAND_HANDLERS.keys()) == {
            "requeue", "cancel", "pause", "resume", "run_validation",
            "publish", "recover_stale",
        }

    def test_each_handler_is_callable(self):
        for key, handler in COMMAND_HANDLERS.items():
            assert callable(handler), f"{key} handler must be callable"


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


class TestOperatorCommandError:
    def test_error_is_value_error(self):
        err = OperatorCommandError("test error")
        assert isinstance(err, ValueError)
        assert str(err) == "test error"
