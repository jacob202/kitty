"""
title: Builder Requeue Packet
author: kitty
version: 0.1
type: action
kind: builder.requeue_packet
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
        packet_id = body.get("payload", {}).get("packet_id", "")
        reason = body.get("payload", {}).get("reason", "UI requeue")
        if not packet_id:
            return {**body, "error": "missing packet_id"}

        result = await asyncio.to_thread(
            subprocess.run,
            [str(KITTY_CLI), "builder", "queue", "operator-release", packet_id, "--reason", reason, "--json"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=60,
        )
        msg = (
            result.stdout.strip()[:500]
            if result.returncode == 0
            else result.stderr.strip()[:500]
            or "requeued"
        )

        if __event_emitter__:
            await __event_emitter__(
                {"type": "status", "data": {"description": msg, "done": True}}
            )
        return {**body, "output": msg}
