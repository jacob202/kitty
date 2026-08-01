"""WorkerSession contract tests — Phase 2 foundation.

Every ``WorkerSession`` backend must pass this suite. The base class defines the
behavioral contract; concrete test classes only supply the factory methods
(``make_session``, ``make_worktree``, ``make_brief``) and any backend-specific
setup.

Do not weaken a test to make a backend pass — fix the backend.
"""

from __future__ import annotations

import abc
import tempfile
from pathlib import Path
from unittest.mock import patch

from gateway.builder_adapters import ShellWorkerSession
from gateway.builder_worker_session import (
    ModelPolicy,
    SessionIdentity,
    WorkerSession,
    WorkerState,
)


class WorkerSessionContract:
    """Abstract contract for WorkerSession backends.

    Concrete backends subclass this and implement only the three factory
    methods. The test methods are the contract — they use ``self.make_session()``
    and must pass for every backend.

    Usage::

        class TestShellWorkerSession(WorkerSessionContract):
            def make_session(self):
                return ShellWorkerSession(["echo"], task_id="test")

            def make_worktree(self):
                return Path(tempfile.mkdtemp())

            def make_brief(self):
                return "contract test brief"
    """

    @abc.abstractmethod
    def make_session(self) -> WorkerSession:
        """Return a configured WorkerSession ready for start()."""

    @abc.abstractmethod
    def make_worktree(self) -> Path:
        """Return a worktree path for start(). Must exist on disk."""

    @abc.abstractmethod
    def make_brief(self) -> str:
        """Return a brief/instruction string for start()."""

    # -- Identity -----------------------------------------------------------

    def test_start_returns_session_identity(self) -> None:
        session = self.make_session()
        identity = session.start(self.make_worktree(), self.make_brief())
        assert isinstance(identity, SessionIdentity)
        assert identity.session_id
        assert identity.backend

    def test_snapshot_returns_session_id(self) -> None:
        session = self.make_session()
        identity = session.start(self.make_worktree(), self.make_brief())
        snap = session.snapshot(identity)
        assert snap.session_id == identity.session_id
        assert isinstance(snap.state, WorkerState)
        assert isinstance(snap.events_count, int)

    # -- Events ------------------------------------------------------------

    def test_events_are_monotonic(self) -> None:
        session = self.make_session()
        identity = session.start(self.make_worktree(), self.make_brief())
        events = session.events(identity)
        assert isinstance(events, list)
        for i, e in enumerate(events):
            assert e.seq == i

    def test_events_no_duplicate_ids(self) -> None:
        session = self.make_session()
        identity = session.start(self.make_worktree(), self.make_brief())
        events = session.events(identity)
        ids = [e.event_id for e in events]
        assert len(ids) == len(set(ids))

    # -- Resume ------------------------------------------------------------

    def test_resume_returns_same_identity(self) -> None:
        session = self.make_session()
        identity = session.start(self.make_worktree(), self.make_brief())
        resumed = session.resume(identity)
        assert resumed.session_id == identity.session_id

    # -- Cancel ------------------------------------------------------------

    def test_cancel_does_not_raise(self) -> None:
        session = self.make_session()
        identity = session.start(self.make_worktree(), self.make_brief())
        session.cancel(identity, reason="contract test")

    # -- Dispose -----------------------------------------------------------

    def test_dispose_marks_not_alive(self) -> None:
        session = self.make_session()
        identity = session.start(self.make_worktree(), self.make_brief())
        session.dispose(identity)
        assert session.is_alive(identity) is False

    def test_dispose_is_idempotent(self) -> None:
        session = self.make_session()
        identity = session.start(self.make_worktree(), self.make_brief())
        session.dispose(identity)
        session.dispose(identity)

    # -- Model policy ------------------------------------------------------

    def test_model_policy_defaults(self) -> None:
        policy = ModelPolicy()
        assert policy.model is None
        assert policy.free_only is False

    def test_model_policy_free_only(self) -> None:
        policy = ModelPolicy(free_only=True, model="kitty-default")
        assert policy.free_only is True


# -- Concrete test classes ------------------------------------------------


class TestShellWorkerSessionContract(WorkerSessionContract):
    """Shell adapter must satisfy the WorkerSession contract."""

    def make_session(self) -> WorkerSession:
        return ShellWorkerSession(["echo", "test"], task_id="contract-test")

    def make_worktree(self) -> Path:
        return Path(tempfile.mkdtemp(prefix="wt-contract-"))

    def make_brief(self) -> str:
        return "contract test brief"

    _fake_run = {"id": 99, "pid": None, "log_path": None, "final_report": {}}

    def test_start_returns_session_identity(self) -> None:
        session = self.make_session()
        with patch("gateway.builder_runner.run_worker", return_value=self._fake_run):
            identity = session.start(self.make_worktree(), self.make_brief())
        assert identity.backend == "shell"
        assert identity.session_id == "99"

    def test_snapshot_returns_session_id(self) -> None:
        session = self.make_session()
        with patch("gateway.builder_runner.run_worker", return_value=self._fake_run):
            identity = session.start(self.make_worktree(), self.make_brief())
        snap = session.snapshot(identity)
        assert snap.session_id == "99"

    def test_dispose_marks_not_alive(self) -> None:
        session = self.make_session()
        with patch("gateway.builder_runner.run_worker", return_value=self._fake_run):
            identity = session.start(self.make_worktree(), self.make_brief())
        session.dispose(identity)
        assert session.is_alive(identity) is False

    def test_resume_returns_same_identity(self) -> None:
        session = self.make_session()
        with patch("gateway.builder_runner.run_worker", return_value=self._fake_run):
            identity = session.start(self.make_worktree(), self.make_brief())
        resumed = session.resume(identity)
        assert resumed.session_id == "99"

    def test_cancel_does_not_raise(self) -> None:
        session = self.make_session()
        with patch("gateway.builder_runner.run_worker", return_value=self._fake_run):
            identity = session.start(self.make_worktree(), self.make_brief())
        session.cancel(identity, reason="contract test")

    def test_dispose_is_idempotent(self) -> None:
        session = self.make_session()
        with patch("gateway.builder_runner.run_worker", return_value=self._fake_run):
            identity = session.start(self.make_worktree(), self.make_brief())
        session.dispose(identity)
        session.dispose(identity)

    def test_events_are_monotonic(self) -> None:
        with patch("gateway.builder_runner.run_worker", return_value=self._fake_run):
            super().test_events_are_monotonic()

    def test_events_no_duplicate_ids(self) -> None:
        with patch("gateway.builder_runner.run_worker", return_value=self._fake_run):
            super().test_events_no_duplicate_ids()
