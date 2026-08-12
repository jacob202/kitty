from __future__ import annotations

import asyncio
import os
from collections.abc import Collection
from typing import Any

import discord
from discord import app_commands
from discord.ext import commands

from .adapters.codex import CodexAdapter
from .config import CommandCenterConfig
from .runner import SubprocessRunner
from .scrub import SecretScrubber
from .service import VibeService
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
    label = "✅ **COMPLETE**" if event_kind == "done" else "❌ **FAILED**"
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
    ) -> None:
        if status_interval_seconds < 0:
            raise ValueError("status_interval_seconds must be non-negative")
        self.service = service
        self.war_room_channel_id = war_room_channel_id
        self.allowed_user_ids = frozenset(allowed_user_ids) if allowed_user_ids is not None else None
        self.allowed_role_ids = frozenset(allowed_role_ids) if allowed_role_ids is not None else None
        self.scrubber = scrubber or SecretScrubber.from_environment()
        self.status_interval_seconds = status_interval_seconds

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
        await interaction.followup.send(f"Task thread: {thread.mention}", ephemeral=True)
        task_card = f"**Task:** {safe_request}\n**Worker:** Codex\n**Mode:** read-only"
        for chunk in split_discord_message(task_card):
            await thread.send(chunk)
        status_message = await thread.send(
            _status_card("🟡 **STARTING**", "Preparing isolated audited run…")
        )

        last_progress_edit_at: float | None = None
        loop = asyncio.get_running_loop()
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

            terminal_state = "✅ **COMPLETE**" if event.kind == "done" else "❌ **FAILED**"
            await status_message.edit(content=_status_card(terminal_state, safe_message))
            for chunk in split_discord_message(
                _result_card(event.kind, safe_message, safe_answer)
            ):
                await thread.send(chunk)

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
    controller = VibeController(
        service,
        war_room_channel_id=config.war_room_channel_id,
        allowed_user_ids=config.allowed_user_ids,
        allowed_role_ids=config.allowed_role_ids,
    )
    guild_id = config.guild_id
    assert guild_id is not None
    guild = discord.Object(id=guild_id)

    @bot.tree.command(name="vibe", description="Run one audited read-only Codex task", guild=guild)
    @app_commands.describe(request="What should Codex inspect or analyze?")
    async def vibe(interaction: discord.Interaction, request: str) -> None:
        await controller.handle(interaction, request)

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
