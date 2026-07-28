"""
title: Builder Recover Stale
author: kitty
version: 0.1
type: action
kind: builder.recover_stale
"""
import asyncio
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
KITTY_CLI = REPO_ROOT / "kitty"


class Action:
    class Valves:
        pass

    class UserValves:
        pass

    def __init__(self):
        pass

    async def action(
        self, body: dict, __event_emitter__=None, __user__=None
    ) -> dict:
        result = await asyncio.to_thread(
            subprocess.run,
            [str(KITTY_CLI), "builder", "queue", "recover", "--json"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=60,
        )
        msg = (
            result.stdout.strip()[:500]
            if result.returncode == 0
            else result.stderr.strip()[:500]
            or "recovery complete"
        )

        if __event_emitter__:
            await __event_emitter__(
                {"type": "status", "data": {"description": msg, "done": True}}
            )
        return {**body, "output": msg}
