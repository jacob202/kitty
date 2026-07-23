"""
title: Builder Control
author: kitty
version: 0.1
type: action
kind: builder.run_next
"""


class Action:
    class Valves:
        pass

    class UserValves:
        pass

    def __init__(self):
        pass

    async def action(self, body: dict, __event_emitter__=None, __user__=None) -> dict:
        packet_id = body.get("payload", {}).get("packet_id", "unknown")
        result = f"Builder run queued for packet {packet_id}"

        if __event_emitter__:
            await __event_emitter__({
                "type": "status",
                "data": {"description": result, "done": True},
            })

        return body
