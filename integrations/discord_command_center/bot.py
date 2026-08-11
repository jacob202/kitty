from __future__ import annotations

import os
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


def _status_card(state: str, detail: str) -> str:
    return (
        f"{state} · **Codex** · read-only\n"
        f"{detail}"
    )


def _result_card(event_kind: str, message: str) -> str:
    label = "✅ **COMPLETE**" if event_kind == "done" else "❌ **FAILED**"
    return (
        f"{label}\n"
        "**Worker:** Codex\n"
        f"**Evidence:** {message}"
    )

def split_discord_message(text: str, limit: int = 1900) -> list[str]:
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
        scrubber: SecretScrubber | None = None,
    ) -> None:
        self.service = service
        self.war_room_channel_id = war_room_channel_id
        self.scrubber = scrubber or SecretScrubber.from_environment()

    async def handle(self, interaction: Any, request: str) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        safe_request = self.scrubber.scrub(request)
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
        await thread.send(f"**Task:** {safe_request}\n**Worker:** Codex\n**Mode:** read-only")
        status_message = await thread.send(
            _status_card("🟡 **STARTING**", "Preparing isolated audited run…")
        )

        async for event in self.service.run(safe_request):
            safe_message = self.scrubber.scrub(event.message)
            if event.kind == "progress":
                await status_message.edit(
                    content=_status_card("🟢 **WORKING**", safe_message)
                )
                continue

            terminal_state = "✅ **COMPLETE**" if event.kind == "done" else "❌ **FAILED**"
            await status_message.edit(content=_status_card(terminal_state, safe_message))
            for chunk in split_discord_message(_result_card(event.kind, safe_message)):
                await thread.send(chunk)


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
    controller = VibeController(service, war_room_channel_id=config.war_room_channel_id)
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
