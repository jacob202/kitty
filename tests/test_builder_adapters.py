"""Tests for gateway/builder_adapters.py — ShellWorkerSession and OpenCodeServerSession."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest

from gateway.builder_adapters import (
    OpenCodeServerSession,
    ShellWorkerSession,
    _extract_event_data,
    _map_opencode_event_type,
    _parse_opencode_events,
)
from gateway.builder_worker_session import (
    ModelPolicy,
    SessionIdentity,
    WorkerEventType,
    WorkerSession,
    WorkerSessionError,
    WorkerSessionNotFoundError,
    WorkerState,
)

# ---------------------------------------------------------------------------
# ShellWorkerSession
# ---------------------------------------------------------------------------


class TestShellWorkerSessionInit:
    def test_rejects_empty_command(self) -> None:
        with pytest.raises(ValueError, match="must be a non-empty list"):
            ShellWorkerSession([])

    def test_accepts_command_list(self) -> None:
        session = ShellWorkerSession(["/bin/echo", "hello"])
        assert session._command == ["/bin/echo", "hello"]

    def test_default_task_id(self) -> None:
        session = ShellWorkerSession(["ls"])
        assert session._task_id == ""

    def test_explicit_task_id(self) -> None:
        session = ShellWorkerSession(["ls"], task_id="task-42")
        assert session._task_id == "task-42"

    def test_is_a_worker_session(self) -> None:
        session = ShellWorkerSession(["ls"])
        assert isinstance(session, WorkerSession)


class TestShellWorkerSessionStart:
    def test_returns_identity_with_shell_backend(self) -> None:
        session = ShellWorkerSession(["echo"], task_id="t1")
        fake_run = {
            "id": 7,
            "pid": None,
            "log_path": None,
            "final_report": {},
        }
        with patch(
            "gateway.builder_runner.run_worker", return_value=fake_run
        ) as mock_run:
            identity = session.start(Path("/tmp/wt"), "brief")

        mock_run.assert_called_once()
        assert identity.backend == "shell"
        assert identity.session_id == "7"

    def test_accepts_model_policy(self) -> None:
        session = ShellWorkerSession(["echo"], task_id="t1")
        fake_run = {"id": 1, "pid": None, "log_path": None, "final_report": {}}
        policy = ModelPolicy(model="deepseek-v4", provider="openrouter")

        with patch(
            "gateway.builder_runner.run_worker", return_value=fake_run
        ) as mock_run:
            session.start(Path("/tmp/wt"), "brief", model_policy=policy)

        call_kwargs = mock_run.call_args.kwargs
        assert call_kwargs["model"] == "deepseek-v4"
        assert call_kwargs["provider"] == "openrouter"

    def test_skips_none_policy(self) -> None:
        session = ShellWorkerSession(["echo"], task_id="t1")
        fake_run = {"id": 1, "pid": None, "log_path": None, "final_report": {}}

        with patch(
            "gateway.builder_runner.run_worker", return_value=fake_run
        ) as mock_run:
            session.start(Path("/tmp/wt"), "brief", model_policy=None)

        call_kwargs = mock_run.call_args.kwargs
        assert call_kwargs["model"] is None
        assert call_kwargs["provider"] is None

    def test_records_pid_when_present(self) -> None:
        session = ShellWorkerSession(["echo"], task_id="t1")
        fake_run = {"id": 7, "pid": 9999, "log_path": None, "final_report": {}}

        with patch("gateway.builder_runner.run_worker", return_value=fake_run):
            identity = session.start(Path("/tmp/wt"), "brief")

        assert session._pids.get(identity.session_id) == 9999


class TestShellWorkerSessionResume:
    def test_resume_known_session(self) -> None:
        session = ShellWorkerSession(["echo"], task_id="t1")
        fake_run = {"id": 7, "pid": None, "log_path": None, "final_report": {}}

        with patch("gateway.builder_runner.run_worker", return_value=fake_run):
            identity = session.start(Path("/tmp/wt"), "brief")

        resumed = session.resume(identity)
        assert resumed.session_id == identity.session_id

    def test_resume_unknown_raises(self) -> None:
        session = ShellWorkerSession(["echo"])
        identity = SessionIdentity(session_id="nonexistent", backend="shell")

        with pytest.raises(WorkerSessionNotFoundError, match="not found"):
            session.resume(identity)


class TestShellWorkerSessionSendInstruction:
    def test_does_not_raise(self) -> None:
        session = ShellWorkerSession(["echo"], task_id="t1")
        identity = SessionIdentity(session_id="1", backend="shell")
        session.send_instruction(identity, "do more")
        # send_instruction is a no-op for shell sessions; must not raise


class TestShellWorkerSessionEvents:
    def test_unknown_session_raises(self) -> None:
        session = ShellWorkerSession(["echo"])
        identity = SessionIdentity(session_id="nonexistent", backend="shell")

        with pytest.raises(WorkerSessionNotFoundError, match="not found"):
            session.events(identity)

    def test_no_log_path_returns_empty(self) -> None:
        session = ShellWorkerSession(["echo"])
        fake_run = {"id": 7, "pid": None, "log_path": None, "final_report": {}}
        identity = SessionIdentity(session_id="7", backend="shell")
        session._runs["7"] = fake_run

        events = session.events(identity)
        assert events == []

    def test_missing_file_returns_empty(self) -> None:
        session = ShellWorkerSession(["echo"])
        fake_run = {"id": 7, "pid": None, "log_path": "/nonexistent/path.log", "final_report": {}}
        identity = SessionIdentity(session_id="7", backend="shell")
        session._runs["7"] = fake_run

        events = session.events(identity)
        assert events == []

    def test_reads_log_lines(self) -> None:
        session = ShellWorkerSession(["echo"])

        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            f.write("line 1\nline 2\n")
            log_path = f.name

        try:
            fake_run = {
                "id": 7,
                "log_path": log_path,
                "final_report": {"outcome": "", "summary": "done"},
                "exit_code": 0,
            }
            identity = SessionIdentity(session_id="7", backend="shell")
            session._runs["7"] = fake_run

            events = session.events(identity)
            # Two TEXT_DELTA lines + MESSAGE_COMPLETE
            assert len(events) >= 2
            assert events[0].type == WorkerEventType.TEXT_DELTA
            assert events[0].data["line"] == "line 1"
            assert events[1].data["line"] == "line 2"
        finally:
            Path(log_path).unlink(missing_ok=True)

    def test_cursor_filters_events(self) -> None:
        session = ShellWorkerSession(["echo"])

        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            f.write("line 1\nline 2\nline 3\n")
            log_path = f.name

        try:
            fake_run = {
                "id": 7,
                "log_path": log_path,
                "final_report": {},
                "exit_code": None,
            }
            identity = SessionIdentity(session_id="7", backend="shell")
            session._runs["7"] = fake_run

            events = session.events(identity, cursor=1)
            # Should start from line 2 (index 1)
            assert len(events) == 2
            assert events[0].data["line"] == "line 2"
            assert events[1].data["line"] == "line 3"
        finally:
            Path(log_path).unlink(missing_ok=True)

    def test_cursor_past_end_returns_empty(self) -> None:
        session = ShellWorkerSession(["echo"])

        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            f.write("one\n")
            log_path = f.name

        try:
            fake_run = {
                "id": 7,
                "log_path": log_path,
                "final_report": {},
                "exit_code": None,
            }
            identity = SessionIdentity(session_id="7", backend="shell")
            session._runs["7"] = fake_run

            events = session.events(identity, cursor=10)
            assert events == []
        finally:
            Path(log_path).unlink(missing_ok=True)

    def test_cancelled_session_emits_cancelled_event(self) -> None:
        session = ShellWorkerSession(["echo"])

        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            f.write("start\n")
            log_path = f.name

        try:
            fake_run = {
                "id": 7,
                "log_path": log_path,
                "final_report": {"outcome": "cancelled"},
                "exit_code": -15,
            }
            identity = SessionIdentity(session_id="7", backend="shell")
            session._runs["7"] = fake_run
            session._cancelled.add("7")

            events = session.events(identity)
            terminal_types = {e.type for e in events}
            assert WorkerEventType.CANCELLED in terminal_types
        finally:
            Path(log_path).unlink(missing_ok=True)

    def test_disposed_session_emits_disposed_event(self) -> None:
        session = ShellWorkerSession(["echo"])

        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            f.write("start\n")
            log_path = f.name

        try:
            fake_run = {
                "id": 7,
                "log_path": log_path,
                "final_report": {},
                "exit_code": 0,
            }
            identity = SessionIdentity(session_id="7", backend="shell")
            session._runs["7"] = fake_run
            session._disposed.add("7")

            events = session.events(identity)
            terminal_types = {e.type for e in events}
            assert WorkerEventType.SESSION_ENDED in terminal_types
        finally:
            Path(log_path).unlink(missing_ok=True)

    def test_nonzero_exit_emits_error_event(self) -> None:
        session = ShellWorkerSession(["echo"])

        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            f.write("start\n")
            log_path = f.name

        try:
            fake_run = {
                "id": 7,
                "log_path": log_path,
                "final_report": {"error": "something went wrong"},
                "exit_code": 1,
            }
            identity = SessionIdentity(session_id="7", backend="shell")
            session._runs["7"] = fake_run

            events = session.events(identity)
            terminal_types = {e.type for e in events}
            assert WorkerEventType.ERROR in terminal_types
        finally:
            Path(log_path).unlink(missing_ok=True)


class TestShellWorkerSessionSnapshot:
    def test_unknown_session_returns_disposed(self) -> None:
        session = ShellWorkerSession(["echo"])
        identity = SessionIdentity(session_id="nonexistent", backend="shell")

        snap = session.snapshot(identity)
        assert snap.state == WorkerState.DISPOSED

    def test_disposed_session(self) -> None:
        session = ShellWorkerSession(["echo"])
        identity = SessionIdentity(session_id="7", backend="shell")
        session._runs["7"] = {"id": 7, "final_report": {}}
        session._disposed.add("7")

        snap = session.snapshot(identity)
        assert snap.state == WorkerState.DISPOSED

    def test_cancelled_session(self) -> None:
        session = ShellWorkerSession(["echo"])
        identity = SessionIdentity(session_id="7", backend="shell")
        session._runs["7"] = {"id": 7, "final_report": {}}
        session._cancelled.add("7")

        snap = session.snapshot(identity)
        assert snap.state == WorkerState.CANCELLED

    def test_completed_on_exit_zero(self) -> None:
        session = ShellWorkerSession(["echo"])
        identity = SessionIdentity(session_id="7", backend="shell")
        session._runs["7"] = {
            "id": 7,
            "final_report": {"model": "deepseek-v4", "changed_paths": ["src/app.py"]},
            "exit_code": 0,
        }

        snap = session.snapshot(identity)
        assert snap.state == WorkerState.COMPLETED
        assert snap.model == "deepseek-v4"
        assert "src/app.py" in snap.changed_paths

    def test_failed_on_nonzero_exit(self) -> None:
        session = ShellWorkerSession(["echo"])
        identity = SessionIdentity(session_id="7", backend="shell")
        session._runs["7"] = {
            "id": 7,
            "final_report": {"error": "boom"},
            "exit_code": 1,
        }

        snap = session.snapshot(identity)
        assert snap.state == WorkerState.FAILED

    def test_running_when_no_exit_code(self) -> None:
        session = ShellWorkerSession(["echo"])
        identity = SessionIdentity(session_id="7", backend="shell")
        session._runs["7"] = {
            "id": 7,
            "final_report": {},
        }

        snap = session.snapshot(identity)
        assert snap.state == WorkerState.RUNNING


class TestShellWorkerSessionCancel:
    def test_marks_cancelled(self) -> None:
        session = ShellWorkerSession(["echo"])
        identity = SessionIdentity(session_id="7", backend="shell")

        session.cancel(identity, reason="test")
        assert "7" in session._cancelled

    def test_no_pid_is_safe(self) -> None:
        session = ShellWorkerSession(["echo"])
        identity = SessionIdentity(session_id="7", backend="shell")

        # Must not raise
        session.cancel(identity)


class TestShellWorkerSessionTranscript:
    def test_returns_path_when_file_exists(self) -> None:
        session = ShellWorkerSession(["echo"])

        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            f.write("log\n")
            log_path = f.name

        try:
            identity = SessionIdentity(session_id="7", backend="shell")
            session._runs["7"] = {"id": 7, "log_path": log_path}

            result = session.transcript(identity)
            assert result == Path(log_path)
        finally:
            Path(log_path).unlink(missing_ok=True)

    def test_returns_none_for_unknown_session(self) -> None:
        session = ShellWorkerSession(["echo"])
        identity = SessionIdentity(session_id="nonexistent", backend="shell")

        assert session.transcript(identity) is None

    def test_returns_none_when_log_path_missing(self) -> None:
        session = ShellWorkerSession(["echo"])
        identity = SessionIdentity(session_id="7", backend="shell")
        session._runs["7"] = {"id": 7, "log_path": None}

        assert session.transcript(identity) is None

    def test_returns_none_when_file_absent(self) -> None:
        session = ShellWorkerSession(["echo"])
        identity = SessionIdentity(session_id="7", backend="shell")
        session._runs["7"] = {"id": 7, "log_path": "/nonexistent/path.log"}

        assert session.transcript(identity) is None


class TestShellWorkerSessionDispose:
    def test_marks_disposed(self) -> None:
        session = ShellWorkerSession(["echo"])
        identity = SessionIdentity(session_id="7", backend="shell")

        session.dispose(identity)
        assert "7" in session._disposed

    def test_idempotent(self) -> None:
        session = ShellWorkerSession(["echo"])
        identity = SessionIdentity(session_id="7", backend="shell")

        session.dispose(identity)
        session.dispose(identity)
        assert "7" in session._disposed


class TestShellWorkerSessionIsAlive:
    def test_false_when_disposed(self) -> None:
        session = ShellWorkerSession(["echo"])
        identity = SessionIdentity(session_id="7", backend="shell")
        session._disposed.add("7")

        assert session.is_alive(identity) is False

    def test_false_when_no_pid(self) -> None:
        session = ShellWorkerSession(["echo"])
        identity = SessionIdentity(session_id="7", backend="shell")
        session._runs["7"] = {"id": 7}
        # no PID recorded

        assert session.is_alive(identity) is False

    @patch("os.kill")
    def test_true_when_process_lives(self, mock_kill: MagicMock) -> None:
        session = ShellWorkerSession(["echo"])
        identity = SessionIdentity(session_id="7", backend="shell")
        session._pids["7"] = 9999

        assert session.is_alive(identity) is True
        mock_kill.assert_called_once_with(9999, 0)

    @patch("os.kill", side_effect=ProcessLookupError)
    def test_false_when_process_dead(self, mock_kill: MagicMock) -> None:
        session = ShellWorkerSession(["echo"])
        identity = SessionIdentity(session_id="7", backend="shell")
        session._pids["7"] = 9999

        assert session.is_alive(identity) is False


# ---------------------------------------------------------------------------
# OpenCodeServerSession
# ---------------------------------------------------------------------------


class TestOpenCodeServerSessionInit:
    def test_strips_trailing_slash(self) -> None:
        session = OpenCodeServerSession("http://localhost:3000/")
        assert session._base_url == "http://localhost:3000"

    def test_sets_bearer_token_when_key_provided(self) -> None:
        session = OpenCodeServerSession("http://localhost:3000", api_key="sk-abc")
        assert session._client.headers.get("Authorization") == "Bearer sk-abc"

    def test_no_auth_header_without_key(self) -> None:
        session = OpenCodeServerSession("http://localhost:3000")
        assert "Authorization" not in session._client.headers

    def test_is_a_worker_session(self) -> None:
        session = OpenCodeServerSession("http://localhost:3000")
        assert isinstance(session, WorkerSession)


class TestOpenCodeServerSessionStart:
    def test_returns_identity_with_opencode_backend(self) -> None:
        session = OpenCodeServerSession("http://localhost:3000")
        fake_response = MagicMock()
        fake_response.json.return_value = {"id": "oc-1", "status": "created"}

        with patch.object(session._client, "post", return_value=fake_response):
            identity = session.start(Path("/tmp/wt"), "brief")

        assert identity.backend == "opencode"
        assert identity.session_id == "oc-1"

    def test_includes_model_policy_in_payload(self) -> None:
        session = OpenCodeServerSession("http://localhost:3000")
        fake_response = MagicMock()
        fake_response.json.return_value = {"id": "oc-1"}

        with patch.object(session._client, "post", return_value=fake_response) as mock_post:
            policy = ModelPolicy(model="deepseek-v4", provider="openrouter")
            session.start(Path("/tmp/wt"), "brief", model_policy=policy)

        call_args = mock_post.call_args
        payload = call_args.kwargs["json"]
        assert payload["model"] == "deepseek-v4"
        assert payload["provider"] == "openrouter"

    def test_raises_on_http_error(self) -> None:
        session = OpenCodeServerSession("http://localhost:3000")

        with patch.object(
            session._client, "post", side_effect=httpx.ConnectError("refused")
        ):
            with pytest.raises(WorkerSessionError, match="session creation failed"):
                session.start(Path("/tmp/wt"), "brief")

    def test_raises_on_missing_id(self) -> None:
        session = OpenCodeServerSession("http://localhost:3000")
        fake_response = MagicMock()
        fake_response.json.return_value = {}

        with patch.object(session._client, "post", return_value=fake_response):
            with pytest.raises(WorkerSessionError, match="no id"):
                session.start(Path("/tmp/wt"), "brief")

    def test_initialises_event_buffer(self) -> None:
        session = OpenCodeServerSession("http://localhost:3000")
        fake_response = MagicMock()
        fake_response.json.return_value = {"id": "oc-1"}

        with patch.object(session._client, "post", return_value=fake_response):
            identity = session.start(Path("/tmp/wt"), "brief")

        assert identity.session_id in session._event_buffers
        assert session._event_buffers[identity.session_id] == []


class TestOpenCodeServerSessionResume:
    def test_resume_known_session(self) -> None:
        session = OpenCodeServerSession("http://localhost:3000")
        session._sessions["oc-1"] = {"id": "oc-1", "status": "running"}
        identity = SessionIdentity(session_id="oc-1", backend="opencode")

        fake_response = MagicMock()
        fake_response.json.return_value = {"id": "oc-1", "status": "running"}

        with patch.object(session._client, "get", return_value=fake_response):
            resumed = session.resume(identity)

        assert resumed.session_id == "oc-1"

    def test_disposed_session_raises(self) -> None:
        session = OpenCodeServerSession("http://localhost:3000")
        session._disposed.add("oc-1")
        identity = SessionIdentity(session_id="oc-1", backend="opencode")

        with pytest.raises(WorkerSessionNotFoundError, match="was disposed"):
            session.resume(identity)

    def test_404_raises_not_found(self) -> None:
        session = OpenCodeServerSession("http://localhost:3000")
        identity = SessionIdentity(session_id="oc-1", backend="opencode")

        fake_response = MagicMock()
        fake_response.status_code = 404

        with patch.object(session._client, "get", return_value=fake_response):
            with pytest.raises(WorkerSessionNotFoundError, match="not found on server"):
                session.resume(identity)


class TestOpenCodeServerSessionSendInstruction:
    def test_sends_prompt(self) -> None:
        session = OpenCodeServerSession("http://localhost:3000")
        session._sessions["oc-1"] = {}
        identity = SessionIdentity(session_id="oc-1", backend="opencode")

        fake_response = MagicMock()
        with patch.object(session._client, "post", return_value=fake_response) as mock_post:
            session.send_instruction(identity, "do more")

        mock_post.assert_called_once()
        assert mock_post.call_args.kwargs["json"] == {"prompt": "do more"}

    def test_disposed_session_raises(self) -> None:
        session = OpenCodeServerSession("http://localhost:3000")
        session._disposed.add("oc-1")
        identity = SessionIdentity(session_id="oc-1", backend="opencode")

        with pytest.raises(WorkerSessionNotFoundError, match="was disposed"):
            session.send_instruction(identity, "do more")


class TestOpenCodeServerSessionEvents:
    def test_disposed_session_returns_empty(self) -> None:
        session = OpenCodeServerSession("http://localhost:3000")
        session._disposed.add("oc-1")
        identity = SessionIdentity(session_id="oc-1", backend="opencode")

        assert session.events(identity) == []

    def test_empty_response_returns_empty(self) -> None:
        session = OpenCodeServerSession("http://localhost:3000")
        session._event_buffers["oc-1"] = []
        identity = SessionIdentity(session_id="oc-1", backend="opencode")

        fake_response = MagicMock()
        fake_response.content = b""
        fake_response.json.return_value = []

        with patch.object(session._client, "get", return_value=fake_response):
            events = session.events(identity)

        assert events == []

    def test_parses_raw_events(self) -> None:
        session = OpenCodeServerSession("http://localhost:3000")
        session._event_buffers["oc-1"] = []
        identity = SessionIdentity(session_id="oc-1", backend="opencode")

        raw_events = [
            {"id": "e1", "type": "session.started", "timestamp": 100.0},
            {"id": "e2", "type": "assistant.message.delta", "timestamp": 101.0, "text": "hi"},
        ]

        fake_response = MagicMock()
        fake_response.content = "x"
        fake_response.json.return_value = raw_events

        with patch.object(session._client, "get", return_value=fake_response):
            events = session.events(identity)

        assert len(events) == 2
        assert events[0].type == WorkerEventType.SESSION_STARTED
        assert events[1].type == WorkerEventType.TEXT_DELTA

    def test_cursor_filters_returned_events(self) -> None:
        session = OpenCodeServerSession("http://localhost:3000")
        session._event_buffers["oc-1"] = [
            MagicMock(seq=0),
            MagicMock(seq=1),
            MagicMock(seq=2),
            MagicMock(seq=3),
        ]
        identity = SessionIdentity(session_id="oc-1", backend="opencode")

        fake_response = MagicMock()
        fake_response.content = ""
        fake_response.json.return_value = []

        with patch.object(session._client, "get", return_value=fake_response):
            events = session.events(identity, cursor=2)

        assert len(events) == 2  # seq 2, 3
        assert events[0].seq == 2
        assert events[1].seq == 3

    def test_non_list_response_handled(self) -> None:
        session = OpenCodeServerSession("http://localhost:3000")
        session._event_buffers["oc-1"] = []
        identity = SessionIdentity(session_id="oc-1", backend="opencode")

        fake_response = MagicMock()
        fake_response.content = "x"
        fake_response.json.return_value = {"error": "not a list"}

        with patch.object(session._client, "get", return_value=fake_response):
            events = session.events(identity)

        assert events == []

    def test_http_error_returns_empty(self) -> None:
        session = OpenCodeServerSession("http://localhost:3000")
        session._event_buffers["oc-1"] = []
        identity = SessionIdentity(session_id="oc-1", backend="opencode")

        with patch.object(
            session._client, "get", side_effect=httpx.ConnectError("refused")
        ):
            events = session.events(identity)

        assert events == []


class TestOpenCodeServerSessionSnapshot:
    def test_disposed_session(self) -> None:
        session = OpenCodeServerSession("http://localhost:3000")
        session._disposed.add("oc-1")
        identity = SessionIdentity(session_id="oc-1", backend="opencode")

        snap = session.snapshot(identity)
        assert snap.state == WorkerState.DISPOSED

    def test_cancelled_session(self) -> None:
        session = OpenCodeServerSession("http://localhost:3000")
        session._cancelled.add("oc-1")
        session._sessions["oc-1"] = {"status": "running"}
        identity = SessionIdentity(session_id="oc-1", backend="opencode")

        snap = session.snapshot(identity)
        assert snap.state == WorkerState.CANCELLED

    def test_completed_status(self) -> None:
        session = OpenCodeServerSession("http://localhost:3000")
        session._sessions["oc-1"] = {
            "id": "oc-1",
            "status": "completed",
            "model": "deepseek-v4",
        }
        identity = SessionIdentity(session_id="oc-1", backend="opencode")

        snap = session.snapshot(identity)
        assert snap.state == WorkerState.COMPLETED
        assert snap.model == "deepseek-v4"

    def test_error_status(self) -> None:
        session = OpenCodeServerSession("http://localhost:3000")
        session._sessions["oc-1"] = {
            "id": "oc-1",
            "status": "error",
            "error": "something broke",
        }
        identity = SessionIdentity(session_id="oc-1", backend="opencode")

        snap = session.snapshot(identity)
        assert snap.state == WorkerState.FAILED
        assert snap.error == "something broke"

    def test_idle_status(self) -> None:
        session = OpenCodeServerSession("http://localhost:3000")
        session._sessions["oc-1"] = {"id": "oc-1", "status": "idle"}
        identity = SessionIdentity(session_id="oc-1", backend="opencode")

        snap = session.snapshot(identity)
        assert snap.state == WorkerState.IDLE

    def test_running_status(self) -> None:
        session = OpenCodeServerSession("http://localhost:3000")
        session._sessions["oc-1"] = {"id": "oc-1", "status": "running"}
        identity = SessionIdentity(session_id="oc-1", backend="opencode")

        snap = session.snapshot(identity)
        assert snap.state == WorkerState.RUNNING

    def test_unknown_status_defaults_to_starting(self) -> None:
        session = OpenCodeServerSession("http://localhost:3000")
        session._sessions["oc-1"] = {"id": "oc-1", "status": "garbage"}
        identity = SessionIdentity(session_id="oc-1", backend="opencode")

        snap = session.snapshot(identity)
        assert snap.state == WorkerState.STARTING

    def test_includes_event_count(self) -> None:
        session = OpenCodeServerSession("http://localhost:3000")
        session._sessions["oc-1"] = {"status": "running"}
        session._event_buffers["oc-1"] = [
            MagicMock(timestamp=1.0),
            MagicMock(timestamp=2.0),
            MagicMock(timestamp=3.0),
        ]
        identity = SessionIdentity(session_id="oc-1", backend="opencode")

        snap = session.snapshot(identity)
        assert snap.events_count == 3
        assert snap.last_activity == 3.0


class TestOpenCodeServerSessionCancel:
    def test_marks_cancelled_and_calls_server(self) -> None:
        session = OpenCodeServerSession("http://localhost:3000")
        identity = SessionIdentity(session_id="oc-1", backend="opencode")

        fake_response = MagicMock()
        with patch.object(session._client, "post", return_value=fake_response) as mock_post:
            session.cancel(identity, reason="test reason")

        assert "oc-1" in session._cancelled
        mock_post.assert_called_once()
        assert mock_post.call_args.kwargs["json"] == {"reason": "test reason"}

    def test_empty_reason_omitted(self) -> None:
        session = OpenCodeServerSession("http://localhost:3000")
        identity = SessionIdentity(session_id="oc-1", backend="opencode")

        fake_response = MagicMock()
        with patch.object(session._client, "post", return_value=fake_response) as mock_post:
            session.cancel(identity)

        assert mock_post.call_args.kwargs["json"] == {}


class TestOpenCodeServerSessionTranscript:
    def test_always_returns_none(self) -> None:
        session = OpenCodeServerSession("http://localhost:3000")
        identity = SessionIdentity(session_id="oc-1", backend="opencode")

        assert session.transcript(identity) is None


class TestOpenCodeServerSessionDispose:
    def test_marks_disposed_and_clears_state(self) -> None:
        session = OpenCodeServerSession("http://localhost:3000")
        session._sessions["oc-1"] = {"id": "oc-1"}
        session._event_buffers["oc-1"] = [MagicMock()]
        identity = SessionIdentity(session_id="oc-1", backend="opencode")

        with patch.object(session._client, "delete") as mock_delete:
            session.dispose(identity)

        assert "oc-1" in session._disposed
        mock_delete.assert_called_once()
        assert "oc-1" not in session._sessions
        assert "oc-1" not in session._event_buffers


class TestOpenCodeServerSessionIsAlive:
    def test_false_when_disposed(self) -> None:
        session = OpenCodeServerSession("http://localhost:3000")
        session._disposed.add("oc-1")
        identity = SessionIdentity(session_id="oc-1", backend="opencode")

        assert session.is_alive(identity) is False

    def test_false_on_404(self) -> None:
        session = OpenCodeServerSession("http://localhost:3000")
        identity = SessionIdentity(session_id="oc-1", backend="opencode")

        fake_response = MagicMock()
        fake_response.status_code = 404

        with patch.object(session._client, "get", return_value=fake_response):
            assert session.is_alive(identity) is False

    def test_true_on_success(self) -> None:
        session = OpenCodeServerSession("http://localhost:3000")
        identity = SessionIdentity(session_id="oc-1", backend="opencode")

        fake_response = MagicMock()
        fake_response.status_code = 200

        with patch.object(session._client, "get", return_value=fake_response):
            assert session.is_alive(identity) is True

    def test_false_on_http_error(self) -> None:
        session = OpenCodeServerSession("http://localhost:3000")
        identity = SessionIdentity(session_id="oc-1", backend="opencode")

        with patch.object(
            session._client, "get", side_effect=httpx.ConnectError("refused")
        ):
            assert session.is_alive(identity) is False


# ---------------------------------------------------------------------------
# Event parsing helpers
# ---------------------------------------------------------------------------


class TestMapOpenCodeEventType:
    def test_maps_known_types(self) -> None:
        cases = [
            ("session.started", WorkerEventType.SESSION_STARTED),
            ("session.resumed", WorkerEventType.SESSION_RESUMED),
            ("assistant.message.delta", WorkerEventType.TEXT_DELTA),
            ("assistant.message.completed", WorkerEventType.MESSAGE_COMPLETE),
            ("tool.start", WorkerEventType.TOOL_START),
            ("tool.end", WorkerEventType.TOOL_END),
            ("command.start", WorkerEventType.COMMAND_START),
            ("command.end", WorkerEventType.COMMAND_END),
            ("file.change", WorkerEventType.FILE_CHANGE),
            ("commit", WorkerEventType.COMMIT),
            ("model.change", WorkerEventType.MODEL_SWITCH),
            ("usage", WorkerEventType.USAGE),
            ("attention.request", WorkerEventType.ATTENTION_REQUEST),
            ("permission.request", WorkerEventType.PERMISSION_REQUEST),
            ("heartbeat", WorkerEventType.HEARTBEAT),
            ("idle", WorkerEventType.IDLE),
            ("error", WorkerEventType.ERROR),
            ("session.cancelled", WorkerEventType.CANCELLED),
            ("session.completed", WorkerEventType.SESSION_ENDED),
        ]
        for raw, expected in cases:
            assert _map_opencode_event_type(raw) == expected

    def test_unknown_type_maps_to_raw(self) -> None:
        assert _map_opencode_event_type("banana.stand") == WorkerEventType.RAW


class TestExtractEventData:
    def test_extracts_known_keys(self) -> None:
        raw = {
            "text": "hello",
            "delta": " hi",
            "message": "full msg",
            "tool": "write",
            "command": "ls",
            "path": "/tmp/test",
            "model": "deepseek-v4",
            "provider": "openrouter",
            "tokens": {"input": 10, "output": 42},
            "exit_code": 0,
            "error": None,
            "reason": "done",
        }
        data = _extract_event_data(raw)
        assert data["text"] == "hello"
        assert data["delta"] == " hi"
        assert data["tokens"] == {"input": 10, "output": 42}

    def test_ignores_unknown_keys(self) -> None:
        raw = {"text": "hi", "banana": "yellow", "count": 7}
        data = _extract_event_data(raw)
        assert data == {"text": "hi"}

    def test_missing_keys_are_not_in_result(self) -> None:
        assert _extract_event_data({}) == {}


class TestParseOpenCodeEvents:
    def test_empty_list(self) -> None:
        result = _parse_opencode_events([], session_id="s1")
        assert result == []

    def test_parses_single_event(self) -> None:
        raw = [{"id": "e1", "type": "session.started", "timestamp": 100.0}]
        result = _parse_opencode_events(raw, session_id="s1", start_seq=5)

        assert len(result) == 1
        event = result[0]
        assert event.event_id == "e1"
        assert event.seq == 5
        assert event.timestamp == 100.0
        assert event.session_id == "s1"
        assert event.type == WorkerEventType.SESSION_STARTED
        assert event.raw_payload == raw[0]

    def test_generates_event_id_when_missing(self) -> None:
        raw = [{"type": "idle"}]
        result = _parse_opencode_events(raw, session_id="s1", start_seq=0)

        assert result[0].event_id == "opencode:s1:0"

    def test_sequential_ids_and_seqs(self) -> None:
        raw = [
            {"type": "session.started"},
            {"type": "assistant.message.delta", "text": "a"},
            {"type": "assistant.message.delta", "text": "b"},
        ]
        result = _parse_opencode_events(raw, session_id="s1", start_seq=0)

        assert result[0].seq == 0
        assert result[1].seq == 1
        assert result[2].seq == 2
        assert result[0].event_id == "opencode:s1:0"
        assert result[1].event_id == "opencode:s1:1"

    def test_preserves_raw_payload(self) -> None:
        raw = [{"id": "x", "type": "error", "extra": "debug-info"}]
        result = _parse_opencode_events(raw, session_id="s1")

        assert result[0].raw_payload == raw[0]
