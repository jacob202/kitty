from __future__ import annotations

import asyncio
from types import SimpleNamespace

import discord
from test_discord_command_center_phase0 import _Interaction, _Thread

from integrations.discord_command_center.bot import VibeController
from integrations.discord_command_center.models import ProgressEvent


class _MentionRecordingThread(_Thread):
    def __init__(self, log: list[str]) -> None:
        super().__init__(log)
        self.send_kwargs: list[dict[str, object]] = []

    async def send(self, content: str, **kwargs: object):
        self.send_kwargs.append(kwargs)
        return await super().send(content, **kwargs)


class _MentionService:
    async def run(self, request: str):
        yield ProgressEvent(kind="progress", message="@everyone progress")
        yield ProgressEvent(kind="done", message="@everyone done", answer="@here answer")


def _has_mentions_disabled(kwargs: dict[str, object]) -> bool:
    mentions = kwargs.get("allowed_mentions")
    return isinstance(mentions, discord.AllowedMentions) and all(
        getattr(mentions, field) is False
        for field in ("everyone", "users", "roles", "replied_user")
    )


def test_thread_output_disables_all_discord_mentions() -> None:
    log: list[str] = []
    interaction = _Interaction(log)
    interaction.user = SimpleNamespace(id=1, roles=[])
    thread = _MentionRecordingThread(log)
    interaction.thread = thread
    interaction.channel.thread = thread

    asyncio.run(VibeController(_MentionService()).handle(interaction, "@everyone inspect"))

    assert len(thread.send_kwargs) == 3
    assert all(_has_mentions_disabled(kwargs) for kwargs in thread.send_kwargs)
