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
