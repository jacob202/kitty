from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

DISABLED_FEATURES = (
    "apps",
    "plugins",
    "browser_use",
    "computer_use",
    "image_generation",
    "multi_agent",
)


@dataclass(frozen=True)
class CodexAdapter:
    executable: str
    model: str

    def command(self, prompt: str, worktree: Path) -> tuple[str, ...]:
        instruction = (
            "You are running in Discord Command Center Phase 0. This is a strictly read-only "
            "analysis run. Do not edit, create, delete, rename, stage, commit, publish, or send "
            "anything. Do not use MCP tools, apps, connectors, browser/computer tools, "
            "image generation, subagents, or external research. Inspect only the local "
            "repository and answer the request concisely.\n\nREQUEST:\n"
            + prompt
        )
        feature_args = tuple(
            value
            for feature in DISABLED_FEATURES
            for value in ("--disable", feature)
        )
        return (
            self.executable,
            *feature_args,
            "exec",
            "--ignore-user-config",
            "--ephemeral",
            "--cd",
            str(worktree),
            "--sandbox",
            "danger-full-access",
            "--json",
            "--model",
            self.model,
            instruction,
        )
