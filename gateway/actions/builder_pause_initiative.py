"""
title: Builder Pause
author: kitty
version: 0.1
type: action
kind: builder.pause_initiative
"""


class Action:
    class Valves:
        pass

    class UserValves:
        pass

    def __init__(self):
        pass

    async def action(self, body: dict, __event_emitter__=None, __user__=None) -> dict:
        initiative_id = body.get("payload", {}).get("initiative_id", "unknown")
        reason = body.get("payload", {}).get("reason", "")
        result = f"Paused initiative {initiative_id}" + (f" — {reason}" if reason else "")

        if __event_emitter__:
            await __event_emitter__({
                "type": "status",
                "data": {"description": result, "done": True},
            })

        return body
