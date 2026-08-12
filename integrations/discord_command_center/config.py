from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_CODEX = "/Applications/ChatGPT.app/Contents/Resources/codex"


@dataclass(frozen=True)
class CommandCenterConfig:
    repo: Path
    codex_executable: str = DEFAULT_CODEX
    codex_model: str = "gpt-5.4-mini"
    run_timeout_seconds: int = 900
    discord_token: str | None = None
    guild_id: int | None = None
    war_room_channel_id: int | None = None
    allowed_user_ids: frozenset[int] = frozenset()
    allowed_role_ids: frozenset[int] = frozenset()

    @classmethod
    def from_env(cls) -> "CommandCenterConfig":
        repo = Path(os.environ.get("COMMAND_CENTER_REPO", Path.cwd())).expanduser().resolve()
        timeout = int(os.environ.get("COMMAND_CENTER_RUN_TIMEOUT_SECONDS", "900"))
        if timeout <= 0:
            raise ValueError("COMMAND_CENTER_RUN_TIMEOUT_SECONDS must be positive")
        return cls(
            repo=repo,
            codex_executable=os.environ.get("COMMAND_CENTER_CODEX_PATH", DEFAULT_CODEX),
            codex_model=os.environ.get("COMMAND_CENTER_CODEX_MODEL", "gpt-5.4-mini"),
            run_timeout_seconds=timeout,
            discord_token=os.environ.get("COMMAND_CENTER_DISCORD_TOKEN"),
            guild_id=_optional_int("COMMAND_CENTER_GUILD_ID"),
            war_room_channel_id=_optional_int("COMMAND_CENTER_WAR_ROOM_CHANNEL_ID"),
            allowed_user_ids=_id_set("COMMAND_CENTER_ALLOWED_USER_IDS"),
            allowed_role_ids=_id_set("COMMAND_CENTER_ALLOWED_ROLE_IDS"),
        )

    def require_discord(self) -> "CommandCenterConfig":
        if not self.discord_token:
            raise RuntimeError("COMMAND_CENTER_DISCORD_TOKEN is required to start the bot")
        if self.guild_id is None:
            raise RuntimeError("COMMAND_CENTER_GUILD_ID is required to start the bot")
        if not self.allowed_user_ids and not self.allowed_role_ids:
            raise RuntimeError(
                "an authorization allowlist is required: set "
                "COMMAND_CENTER_ALLOWED_USER_IDS or COMMAND_CENTER_ALLOWED_ROLE_IDS"
            )
        return self


def _optional_int(name: str) -> int | None:
    value = os.environ.get(name)
    if value is None or not value.strip():
        return None
    parsed = int(value)
    if parsed <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return parsed


def _id_set(name: str) -> frozenset[int]:
    value = os.environ.get(name, "")
    if not value.strip():
        return frozenset()
    parsed: set[int] = set()
    for item in value.split(","):
        token = item.strip()
        if not token:
            continue
        if not token.isdigit() or int(token) <= 0:
            raise ValueError(f"{name} must contain positive integer IDs")
        parsed.add(int(token))
    return frozenset(parsed)
