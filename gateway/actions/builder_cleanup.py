"""
title: Builder Cleanup
author: kitty
version: 0.1
type: action
kind: builder.cleanup
"""


class Action:
    class Valves:
        pass

    class UserValves:
        pass

    def __init__(self):
        pass

    async def action(self, body: dict, __event_emitter__=None, __user__=None) -> dict:
        count = body.get("payload", {}).get("count", 0)
        result = f"Builder cleanup complete — {count} zombie tasks cancelled"

        if __event_emitter__:
            await __event_emitter__({
                "type": "status",
                "data": {"description": result, "done": True},
            })

        return body
