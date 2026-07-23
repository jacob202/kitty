"""
title: Repair Dismiss
author: kitty
version: 0.1
type: action
kind: repair.dismiss
"""


class Action:
    class Valves:
        pass

    class UserValves:
        pass

    def __init__(self):
        pass

    async def action(self, body: dict, __event_emitter__=None, __user__=None) -> dict:
        label = body.get("payload", {}).get("label", "a repair item")
        result = f"Dismissed: {label}"

        if __event_emitter__:
            await __event_emitter__({
                "type": "status",
                "data": {"description": result, "done": True},
            })

        return body
