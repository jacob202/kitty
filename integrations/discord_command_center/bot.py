from __future__ import annotations

import asyncio
import os
from collections.abc import Collection
from contextlib import suppress
from typing import Any

import discord
from discord import app_commands
from discord.ext import commands

from .adapters.codex import CodexAdapter
from .config import CommandCenterConfig
from .runner import SubprocessRunner
from .scrub import SecretScrubber
from .service import VibeService
from .tasks import TaskRegistry
from .workspace import GitWorktreeManager

DISCORD_MESSAGE_LIMIT = 1900


def _bounded_text(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    if limit <= 1:
        return text[:limit]
    return text[: limit - 1] + "…"


def _status_card(state: str, detail: str) -> str:
    prefix = f"{state} · **Codex** · read-only\n"
    return prefix + _bounded_text(detail, DISCORD_MESSAGE_LIMIT - len(prefix))


def _result_card(event_kind: str, message: str, answer: str | None = None) -> str:
    if event_kind == "done":
        label = "✅ **COMPLETE**"
    elif event_kind == "cancelled":
        label = "⚪ **CANCELLED**"
    else:
        label = "❌ **FAILED**"
    result = f"{label}\n**Worker:** Codex\n"
    if answer:
        result += f"**Result:** {answer}\n"
    return result + f"**Evidence:** {message}"

def split_discord_message(text: str, limit: int = DISCORD_MESSAGE_LIMIT) -> list[str]:
    if limit <= 0:
        raise ValueError("limit must be positive")
    if not text:
        return [""]
    return [text[index : index + limit] for index in range(0, len(text), limit)]


class VibeController:
    def __init__(
        self,
        service: VibeService,
        *,
        war_room_channel_id: int | None = None,
        allowed_user_ids: Collection[int] | None = None,
        allowed_role_ids: Collection[int] | None = None,
        scrubber: SecretScrubber | None = None,
        status_interval_seconds: float = 2.0,
        registry: TaskRegistry | None = None,
    ) -> None:
        if status_interval_seconds < 0:
            raise ValueError("status_interval_seconds must be non-negative")
        self.service = service
        self.war_room_channel_id = war_room_channel_id
        self.allowed_user_ids = frozenset(allowed_user_ids) if allowed_user_ids is not None else None
        self.allowed_role_ids = frozenset(allowed_role_ids) if allowed_role_ids is not None else None
        self.scrubber = scrubber or SecretScrubber.from_environment()
        self.status_interval_seconds = status_interval_seconds
        self.registry = registry or TaskRegistry()

    async def handle(self, interaction: Any, request: str) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        safe_request = self.scrubber.scrub(request)
        if not self._authorized(interaction):
            await interaction.followup.send(
                "You are not authorized to start Command Center tasks.", ephemeral=True
            )
            return
        channel = interaction.channel
        if channel is None or not hasattr(channel, "create_thread"):
            await interaction.followup.send(
                "Command Center needs to be used from a text channel.", ephemeral=True
            )
            return
        channel_id = getattr(channel, "id", None)
        if self.war_room_channel_id is not None and channel_id != self.war_room_channel_id:
            await interaction.followup.send(
                "Use /vibe in the configured #war-room channel.", ephemeral=True
            )
            return

        owner_id = getattr(getattr(interaction, "user", None), "id", None)
        reservation = self.registry.reserve(owner_id)
        if reservation is None:
            await interaction.followup.send(
                "Command Center is at capacity or you already have an active task; "
                "wait for a task to finish or cancel it before starting another.",
                ephemeral=True,
            )
            return

        status_message = None
        try:
            title = "vibe-" + "-".join(safe_request.lower().split())[:70]
            thread = await channel.create_thread(
                name=title or "vibe-task",
                type=discord.ChannelType.private_thread,
                invitable=False,
                reason="Discord Command Center /vibe",
            )
            try:
                await thread.add_user(interaction.user)
            except (discord.HTTPException, AttributeError) as exc:
                await interaction.followup.send(
                    "Command Center could not add you to the private task thread; "
                    "the task was not started. "
                    f"({type(exc).__name__})",
                    ephemeral=True,
                )
                return
            current_task = asyncio.current_task()
            if current_task is None:
                raise RuntimeError("Command Center task callback has no asyncio task")
            self.registry.register(
                reservation,
                current_task,
                thread_id=getattr(thread, "id", None),
            )
            await interaction.followup.send(
                f"Task thread: {thread.mention} · Task ID: `{reservation.task_id}`",
                ephemeral=True,
            )
            task_card = (
                f"**Task:** {safe_request}\n**Task ID:** `{reservation.task_id}`\n"
                "**Worker:** Codex\n**Mode:** read-only"
            )
            for chunk in split_discord_message(task_card):
                await thread.send(chunk)
            status_message = await thread.send(
                _status_card("🟡 **STARTING**", "Preparing isolated audited run…")
            )

            last_progress_edit_at: float | None = None
            loop = asyncio.get_running_loop()
            try:
                async for event in self.service.run(safe_request):
                    safe_message = self.scrubber.scrub(event.message)
                    safe_answer = self.scrubber.scrub(event.answer or "") or None
                    if event.kind == "progress":
                        now = loop.time()
                        if (
                            last_progress_edit_at is None
                            or now - last_progress_edit_at >= self.status_interval_seconds
                        ):
                            await status_message.edit(
                                content=_status_card("🟢 **WORKING**", safe_message)
                            )
                            last_progress_edit_at = now
                        continue

                    terminal_state = (
                        "✅ **COMPLETE**"
                        if event.kind == "done"
                        else "❌ **FAILED**"
                    )
                    await status_message.edit(content=_status_card(terminal_state, safe_message))
                    for chunk in split_discord_message(
                        _result_card(event.kind, safe_message, safe_answer)
                    ):
                        await thread.send(chunk)
                    break
            except asyncio.CancelledError:
                cancelled_message = (
                    "Task cancellation requested. The worker was stopped; the existing "
                    "bounded cleanup and audit path is preserving any uncertain worktree."
                )
                with suppress(Exception):
                    await status_message.edit(
                        content=_status_card("⚪ **CANCELLED**", cancelled_message)
                    )
                with suppress(Exception):
                    await thread.send(_result_card("cancelled", cancelled_message))
                return
        finally:
            self.registry.release(reservation.task_id)

    async def cancel(self, interaction: Any, task_id: str | None = None) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        if not self._authorized(interaction):
            await interaction.followup.send(
                "You are not authorized to control Command Center tasks.", ephemeral=True
            )
            return
        owner_id = getattr(getattr(interaction, "user", None), "id", None)
        channel_id = getattr(getattr(interaction, "channel", None), "id", None)
        entry = self.registry.find(
            owner_id=owner_id,
            task_id=task_id,
            thread_id=None if task_id else channel_id,
        )
        if entry is None or entry.task is None or entry.task.done():
            await interaction.followup.send(
                "No active Command Center task matched that task ID or thread.",
                ephemeral=True,
            )
            return
        entry.task.cancel()
        await interaction.followup.send(
            f"Cancellation requested for `{entry.task_id}`.", ephemeral=True
        )

    async def status(self, interaction: Any, task_id: str | None = None) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        if not self._authorized(interaction):
            await interaction.followup.send(
                "You are not authorized to view Command Center tasks.", ephemeral=True
            )
            return
        owner_id = getattr(getattr(interaction, "user", None), "id", None)
        entries = (
            [entry]
            if task_id
            and (entry := self.registry.find(owner_id=owner_id, task_id=task_id)) is not None
            else list(self.registry.for_owner(owner_id)) if task_id is None else []
        )
        if not entries:
            await interaction.followup.send(
                "No active Command Center tasks.", ephemeral=True
            )
            return
        now = asyncio.get_running_loop().time()
        lines = ["**Active Command Center tasks:**"]
        for entry in entries:
            elapsed = max(0, int(now - entry.created_at))
            thread = str(entry.thread_id) if entry.thread_id is not None else "starting"
            lines.append(f"`{entry.task_id}` · thread `{thread}` · active {elapsed}s")
        await interaction.followup.send("\n".join(lines), ephemeral=True)

    def _authorized(self, interaction: Any) -> bool:
        if self.allowed_user_ids is None and self.allowed_role_ids is None:
            return True
        user = getattr(interaction, "user", None)
        user_id = getattr(user, "id", None)
        if user_id in (self.allowed_user_ids or frozenset()):
            return True
        role_ids = {
            getattr(role, "id", None)
            for role in (getattr(user, "roles", ()) or ())
        }
        return bool(role_ids & (self.allowed_role_ids or frozenset()))


def create_bot(config: CommandCenterConfig) -> commands.Bot:
    config.require_discord()
    intents = discord.Intents.none()
    intents.guilds = True
    bot = commands.Bot(command_prefix=commands.when_mentioned, intents=intents)
    service = VibeService(
        workspace=GitWorktreeManager(repo=config.repo),
        adapter=CodexAdapter(config.codex_executable, config.codex_model),
        runner=SubprocessRunner(),
        timeout_seconds=config.run_timeout_seconds,
        environment=os.environ,
    )
    registry = TaskRegistry(
        max_concurrent_runs=config.max_concurrent_runs,
        max_runs_per_user=config.max_runs_per_user,
    )
    controller = VibeController(
        service,
        war_room_channel_id=config.war_room_channel_id,
        allowed_user_ids=config.allowed_user_ids,
        allowed_role_ids=config.allowed_role_ids,
        registry=registry,
    )
    guild_id = config.guild_id
    assert guild_id is not None
    guild = discord.Object(id=guild_id)

    @bot.tree.command(name="vibe", description="Run one audited read-only Codex task", guild=guild)
    @app_commands.describe(request="What should Codex inspect or analyze?")
    async def vibe(interaction: discord.Interaction, request: str) -> None:
        await controller.handle(interaction, request)

    @bot.tree.command(
        name="vibe-cancel",
        description="Cancel one of your active Command Center tasks",
        guild=guild,
    )
    @app_commands.describe(task_id="Optional task ID; omit this inside its private task thread")
    async def vibe_cancel(interaction: discord.Interaction, task_id: str | None = None) -> None:
        await controller.cancel(interaction, task_id)

    @bot.tree.command(
        name="vibe-status",
        description="Show your active Command Center tasks",
        guild=guild,
    )
    @app_commands.describe(task_id="Optional task ID to inspect")
    async def vibe_status(interaction: discord.Interaction, task_id: str | None = None) -> None:
        await controller.status(interaction, task_id)

    original_setup_hook = bot.setup_hook

    async def setup_hook() -> None:
        await original_setup_hook()
        await bot.tree.sync(guild=guild)

    bot.setup_hook = setup_hook  # type: ignore[method-assign]
    return bot


def main() -> int:
    config = CommandCenterConfig.from_env().require_discord()
    bot = create_bot(config)
    assert config.discord_token is not None
    bot.run(config.discord_token)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
