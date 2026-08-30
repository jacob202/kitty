"""Tests for agent_runner — spawn, status, listing, stopping."""

from unittest.mock import AsyncMock, patch

import pytest

from gateway.agent_runner import (
    AGENT_PRESETS,
    _is_finished,
    await_completion,
    get_output,
    get_status,
    list_agents,
    stop,
)
from gateway.autonomy_state import AutonomyState


async def _noop_agent_loop(*args, **kwargs) -> None:
    """Substitute real LLM loop so create_task schedules an awaited coroutine."""


class TestPresets:
    def test_all_presets_defined(self):
        assert len(AGENT_PRESETS) == 5
        for name in ("explorer", "planner", "coder", "reviewer", "researcher"):
            assert name in AGENT_PRESETS

    def test_each_preset_has_required_fields(self):
        for name, preset in AGENT_PRESETS.items():
            assert "description" in preset, f"{name} missing description"
            assert "system_prompt" in preset, f"{name} missing system_prompt"
            assert "max_iterations" in preset, f"{name} missing max_iterations"
            assert preset["max_iterations"] > 0

    def test_spawn_unknown_type_raises(self):
        import asyncio

        with pytest.raises(ValueError, match="Unknown agent type"):
            asyncio.run(
                __import__("gateway.agent_runner", fromlist=["spawn"]).spawn(
                    "test", agent_type="bogus"
                )
            )


class TestIsFinished:
    def test_final_answer_detected(self):
        assert _is_finished("Here is my final answer: the answer is 42.")

    def test_conclusion_detected(self):
        assert _is_finished("In conclusion, we should use PostgreSQL.")

    def test_summarize_detected(self):
        assert _is_finished("To summarize: three main points.")

    def test_mid_thought_not_finished(self):
        assert not _is_finished("Let me think about this more carefully.")
        assert not _is_finished("The next step would be to research further.")


class TestListStop:
    def test_list_agents_returns_list(self):
        agents = list_agents(limit=5)
        assert isinstance(agents, list)

    def test_stop_nonexistent_returns_false(self):
        assert stop(999999) is False


class TestGetStatusNotFound:
    def test_nonexistent_session(self):
        result = get_status(999999)
        assert result["status"] == "not_found"

    def test_nonexistent_output_empty(self):
        result = get_output(999999)
        assert result == ""


@pytest.mark.asyncio
class TestSpawnAndRun:
    async def test_spawn_explorer_creates_session(self):
        from unittest.mock import patch

        from gateway.agent_runner import spawn as agent_spawn

        # Mock the background task so it doesn't actually call LLMs
        with patch("gateway.agent_runner._run_agent_loop", new=_noop_agent_loop):
            session_id = await agent_spawn(
                "test goal",
                agent_type="explorer",
                max_iterations=1,
            )
            assert isinstance(session_id, int)
            assert session_id > 0

    async def test_spawn_with_extra_context(self):
        from unittest.mock import patch

        from gateway.agent_runner import spawn as agent_spawn

        with patch("gateway.agent_runner._run_agent_loop", new=_noop_agent_loop):
            session_id = await agent_spawn(
                "research cats",
                agent_type="researcher",
                extra_context="Cats are mammals.",
                metadata={"priority": "high"},
            )
            assert session_id > 0

    async def test_spawn_all_preset_types(self):
        from unittest.mock import patch

        from gateway.agent_runner import spawn as agent_spawn

        with patch("gateway.agent_runner._run_agent_loop", new=_noop_agent_loop):
            for agent_type in AGENT_PRESETS:
                session_id = await agent_spawn(
                    f"test {agent_type}",
                    agent_type=agent_type,
                    max_iterations=1,
                )
                assert session_id > 0


@pytest.mark.asyncio
class TestAwaitCompletion:
    async def test_returns_when_agent_completes(self):
        statuses = [{"status": "active"}, {"status": "completed", "iterations": 2}]

        with patch("gateway.agent_runner.get_status", side_effect=statuses), patch(
            "gateway.agent_runner.asyncio.sleep", new=AsyncMock()
        ):
            result = await await_completion(1, timeout=10, poll=1)
        assert result["status"] == "completed"

    async def test_timeout_returns_last_status(self):
        with patch(
            "gateway.agent_runner.get_status",
            return_value={"status": "active", "iterations": 1},
        ), patch("gateway.agent_runner.asyncio.sleep", new=AsyncMock()):
            result = await await_completion(1, timeout=2, poll=1)
        assert result["status"] == "active"


@pytest.mark.asyncio
async def test_llm_failure_finishes_agent_as_failed(tmp_path, monkeypatch):
    import gateway.agent_runner as agent_runner
    import gateway.autonomy_state as autonomy_state

    monkeypatch.setattr(autonomy_state, "STATE_DB", tmp_path / "autonomy.db")
    autonomy_state.init_db()
    state = AutonomyState.start_new("fail visibly")

    with patch("gateway.llm_client.route_model", return_value="test-model"), patch(
        "gateway.llm_client.call_llm", side_effect=RuntimeError("provider down")
    ):
        await agent_runner._run_agent_loop(
            state.session_id or 0,
            "fail visibly",
            "system",
            "test-model",
            1,
            0.0,
            False,
        )

    assert agent_runner.get_status(state.session_id or 0)["status"] == "failed"


@pytest.mark.asyncio
async def test_stop_cancels_registered_agent_task(tmp_path, monkeypatch):
    import asyncio

    import gateway.agent_runner as agent_runner
    import gateway.autonomy_state as autonomy_state

    monkeypatch.setattr(autonomy_state, "STATE_DB", tmp_path / "autonomy.db")
    autonomy_state.init_db()
    state = AutonomyState.start_new("cancel visibly")
    task = asyncio.create_task(asyncio.sleep(60))
    session_id = state.session_id or 0
    agent_runner._AGENT_TASKS[session_id] = task

    assert agent_runner.stop(session_id) is True
    with pytest.raises(asyncio.CancelledError):
        await task


class TestRestartTruth:
    """A Gateway restart destroys _AGENT_TASKS; the durable rows must stop lying.

    `active` means "an executor is working this session". After the process that
    owned the executor is gone, no such executor exists, so the row is
    `interrupted` — not `failed`, which would claim the work was tried and lost.
    """

    @staticmethod
    def _isolate(tmp_path, monkeypatch):
        import gateway.autonomy_state as autonomy_state

        monkeypatch.setattr(autonomy_state, "STATE_DB", tmp_path / "autonomy.db")
        autonomy_state.init_db()
        return autonomy_state

    def test_active_session_becomes_interrupted_at_startup(self, tmp_path, monkeypatch):
        autonomy_state = self._isolate(tmp_path, monkeypatch)
        state = AutonomyState.start_new("survive a restart")

        assert autonomy_state.interrupt_active_sessions() == 1
        assert get_status(state.session_id or 0)["status"] == "interrupted"

    def test_second_reconcile_is_a_no_op(self, tmp_path, monkeypatch):
        autonomy_state = self._isolate(tmp_path, monkeypatch)
        state = AutonomyState.start_new("restart twice")

        assert autonomy_state.interrupt_active_sessions() == 1
        assert autonomy_state.interrupt_active_sessions() == 0
        assert get_status(state.session_id or 0)["status"] == "interrupted"

    def test_partial_output_is_preserved_through_reconciliation(self, tmp_path, monkeypatch):
        autonomy_state = self._isolate(tmp_path, monkeypatch)
        state = AutonomyState.start_new("keep the partial work")
        state.record_step("assistant", content="PHASE: OBSERVE — got this far")
        state.record_step("assistant", content="PHASE: ORIENT — and this far")

        autonomy_state.interrupt_active_sessions()

        session_id = state.session_id or 0
        status = get_status(session_id)
        assert status["status"] == "interrupted"
        assert status["iterations"] == 2
        assert status["total_steps"] == 2
        assert "and this far" in get_output(session_id)

    @pytest.mark.parametrize("terminal", ["completed", "failed", "cancelled", "interrupted"])
    def test_already_terminal_sessions_are_untouched(self, tmp_path, monkeypatch, terminal):
        autonomy_state = self._isolate(tmp_path, monkeypatch)
        state = AutonomyState.start_new(f"already {terminal}")
        state.finish(terminal)

        assert autonomy_state.interrupt_active_sessions() == 0
        assert get_status(state.session_id or 0)["status"] == terminal

    def test_reconcile_cannot_overwrite_a_status_that_won_the_race(self, tmp_path, monkeypatch):
        """stop() and reconciliation can land in either order; neither may clobber."""
        autonomy_state = self._isolate(tmp_path, monkeypatch)
        cancelled = AutonomyState.start_new("cancelled first")
        still_active = AutonomyState.start_new("never stopped")
        assert stop(cancelled.session_id or 0) is True

        assert autonomy_state.interrupt_active_sessions() == 1

        assert get_status(cancelled.session_id or 0)["status"] == "cancelled"
        assert get_status(still_active.session_id or 0)["status"] == "interrupted"

    @pytest.mark.asyncio
    async def test_interrupted_is_terminal_for_await_completion(self):
        sleeps = AsyncMock()
        with patch(
            "gateway.agent_runner.get_status",
            return_value={"status": "interrupted", "iterations": 2},
        ), patch("gateway.agent_runner.asyncio.sleep", new=sleeps):
            result = await await_completion(1, timeout=30, poll=1)
        assert result["status"] == "interrupted"
        assert sleeps.await_count == 1, "interrupted must end the poll loop, not time out"


class TestZeroStepSessionIsNotMissing:
    """A durable row with no steps yet is a real session, not a 404."""

    def test_session_with_no_steps_reports_itself_truthfully(self, tmp_path, monkeypatch):
        import gateway.autonomy_state as autonomy_state

        monkeypatch.setattr(autonomy_state, "STATE_DB", tmp_path / "autonomy.db")
        autonomy_state.init_db()
        state = AutonomyState.start_new("spawned but not yet stepped")

        status = get_status(state.session_id or 0)

        assert status["status"] == "active"
        assert status["goal"] == "spawned but not yet stepped"
        assert status["iterations"] == 0
        assert status["total_steps"] == 0
        assert status["last_output_snippet"] == ""

    def test_genuinely_missing_session_is_still_not_found(self, tmp_path, monkeypatch):
        import gateway.autonomy_state as autonomy_state

        monkeypatch.setattr(autonomy_state, "STATE_DB", tmp_path / "autonomy.db")
        autonomy_state.init_db()

        assert get_status(4242)["status"] == "not_found"


class TestAgentStatusRoute:
    @pytest.mark.asyncio
    async def test_interrupted_session_returns_its_preserved_output(self):
        from gateway.routes.extended import agent_status

        with patch(
            "gateway.agent_runner.get_status",
            return_value={"session_id": 7, "status": "interrupted"},
        ), patch("gateway.agent_runner.get_output", return_value="partial work"):
            result = await agent_status(7)

        assert result["output"] == "partial work"

    @pytest.mark.asyncio
    async def test_missing_session_is_a_404(self):
        from fastapi import HTTPException

        from gateway.routes.extended import agent_status

        with patch(
            "gateway.agent_runner.get_status",
            return_value={"session_id": 9, "status": "not_found"},
        ):
            with pytest.raises(HTTPException) as excinfo:
                await agent_status(9)
        assert excinfo.value.status_code == 404
