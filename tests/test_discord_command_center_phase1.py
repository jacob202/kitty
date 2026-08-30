from __future__ import annotations

import asyncio
from contextlib import suppress
from pathlib import Path
from types import SimpleNamespace

import discord
import pytest
from test_discord_command_center_phase0 import _Interaction

from integrations.discord_command_center.bot import VibeController, create_bot
from integrations.discord_command_center.config import CommandCenterConfig
from integrations.discord_command_center.models import ProgressEvent
from integrations.discord_command_center.tasks import TaskRegistry


def test_config_reads_positive_task_limits(monkeypatch) -> None:
    monkeypatch.setenv("COMMAND_CENTER_REPO", "/tmp/command-center")
    monkeypatch.setenv("COMMAND_CENTER_MAX_CONCURRENT_RUNS", "3")
    monkeypatch.setenv("COMMAND_CENTER_MAX_RUNS_PER_USER", "2")
    monkeypatch.setenv("COMMAND_CENTER_MAX_REQUEST_CHARS", "4000")

    config = CommandCenterConfig.from_env()

    assert config.max_concurrent_runs == 3
    assert config.max_runs_per_user == 2
    assert config.max_request_chars == 4000


def test_bot_registers_request_cancel_and_status_commands() -> None:
    config = CommandCenterConfig(
        repo=Path("/tmp/command-center"),
        discord_token="token",
        guild_id=1,
        allowed_user_ids=frozenset({1}),
    )

    bot = create_bot(config)

    assert {command.name for command in bot.tree.get_commands(guild=discord.Object(id=1))} == {
        "vibe",
        "vibe-cancel",
        "vibe-status",
    }


@pytest.mark.parametrize(
    "name",
    [
        "COMMAND_CENTER_MAX_CONCURRENT_RUNS",
        "COMMAND_CENTER_MAX_RUNS_PER_USER",
        "COMMAND_CENTER_MAX_REQUEST_CHARS",
    ],
)
def test_config_rejects_non_positive_task_limits(monkeypatch, name: str) -> None:
    monkeypatch.setenv("COMMAND_CENTER_REPO", "/tmp/command-center")
    monkeypatch.setenv(name, "0")

    with pytest.raises(ValueError, match="positive"):
        CommandCenterConfig.from_env()


def test_controller_rejects_oversized_request_before_admission() -> None:
    log: list[str] = []
    interaction = _Interaction(log)
    interaction.user = SimpleNamespace(id=1, roles=[])
    registry = TaskRegistry(max_concurrent_runs=1, max_runs_per_user=1)
    controller = VibeController(_IdleService(), registry=registry, max_request_chars=4)

    asyncio.run(controller.handle(interaction, "12345"))

    assert "create_thread" not in log
    assert registry.for_owner(1) == ()
    assert any("too long" in message.lower() for message in interaction.followup.messages)


def test_task_registry_enforces_global_and_per_user_limits() -> None:
    registry = TaskRegistry(max_concurrent_runs=2, max_runs_per_user=1)

    first = registry.reserve(1)
    assert first is not None
    assert registry.reserve(1) is None
    second = registry.reserve(2)
    assert second is not None
    assert registry.reserve(3) is None

    registry.release(first.task_id)

    third = registry.reserve(1)
    assert third is not None


def test_task_registry_resolves_owner_and_thread() -> None:
    async def exercise() -> None:
        registry = TaskRegistry()
        reservation = registry.reserve(7)
        assert reservation is not None
        current = asyncio.current_task()
        assert current is not None
        registry.register(reservation, current, thread_id=99)

        assert registry.find(task_id=reservation.task_id, owner_id=7) is not None
        assert registry.find(thread_id=99, owner_id=7) is not None
        assert registry.find(task_id=reservation.task_id, owner_id=8) is None

        registry.release(reservation.task_id)
        assert registry.find(task_id=reservation.task_id, owner_id=7) is None

    asyncio.run(exercise())


def test_controller_rejects_saturated_admission_before_thread_creation() -> None:
    log: list[str] = []
    interaction = _Interaction(log)
    interaction.user = SimpleNamespace(id=1, roles=[])
    registry = TaskRegistry(max_concurrent_runs=1, max_runs_per_user=1)
    reservation = registry.reserve(99)
    assert reservation is not None
    controller = VibeController(_IdleService(), registry=registry)

    asyncio.run(controller.handle(interaction, "inspect repo"))

    assert "create_thread" not in log
    assert any("capacity" in message.lower() for message in interaction.followup.messages)
    registry.release(reservation.task_id)


class _IdleService:
    async def run(self, request: str):
        yield ProgressEvent(kind="done", message="audit clean")


class _BlockingService:
    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def run(self, request: str):
        self.started.set()
        yield ProgressEvent(kind="progress", message="working")
        await self.release.wait()
        yield ProgressEvent(kind="done", message="audit clean")


def test_controller_cancel_posts_terminal_state_and_releases_slot() -> None:
    async def exercise() -> None:
        log: list[str] = []
        interaction = _Interaction(log)
        interaction.user = SimpleNamespace(id=1, roles=[])
        interaction.channel.id = 10
        interaction.thread.id = 20
        service = _BlockingService()
        registry = TaskRegistry(max_concurrent_runs=1, max_runs_per_user=1)
        controller = VibeController(service, registry=registry)

        running = asyncio.create_task(controller.handle(interaction, "inspect repo"))
        await service.started.wait()
        active = registry.find(thread_id=20, owner_id=1)
        assert active is not None

        cancel_interaction = _Interaction([])
        cancel_interaction.user = SimpleNamespace(id=1, roles=[])
        cancel_interaction.channel.id = 20
        await controller.cancel(cancel_interaction, active.task_id)
        await running

        assert any("cancellation requested" in message.lower() for message in cancel_interaction.followup.messages)
        assert any("cancelled" in message.lower() for message in interaction.thread.messages)
        assert registry.find(task_id=active.task_id, owner_id=1) is None

    asyncio.run(exercise())


def test_controller_status_is_owner_only_and_exposes_no_request_text() -> None:
    async def exercise() -> None:
        registry = TaskRegistry()
        reservation = registry.reserve(1)
        assert reservation is not None
        task = asyncio.create_task(asyncio.Event().wait())
        registry.register(reservation, task, thread_id=42)
        controller = VibeController(_IdleService(), registry=registry)

        interaction = _Interaction([])
        interaction.user = SimpleNamespace(id=1, roles=[])
        await controller.status(interaction)
        assert reservation.task_id in interaction.followup.messages[0]
        assert "42" in interaction.followup.messages[0]
        assert "request" not in interaction.followup.messages[0].lower()

        unauthorized = _Interaction([])
        unauthorized.user = SimpleNamespace(id=2, roles=[])
        await controller.status(unauthorized, reservation.task_id)
        assert unauthorized.followup.messages == ["No active Command Center tasks."]

        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
        registry.release(reservation.task_id)

    asyncio.run(exercise())
