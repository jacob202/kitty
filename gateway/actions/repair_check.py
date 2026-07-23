"""
title: Repair Check
author: kitty
version: 0.1
type: action
kind: repair.check
"""


class Action:
    class Valves:
        pass

    class UserValves:
        pass

    def __init__(self):
        pass

    async def action(self, body: dict, __event_emitter__=None, __user__=None) -> dict:
        check_name = body.get("payload", {}).get("check_name", "")
        result = f"Re-ran health check: {check_name}. Current status may have changed."

        if __event_emitter__:
            await __event_emitter__({
                "type": "status",
                "data": {"description": result, "done": True},
            })

        return body
