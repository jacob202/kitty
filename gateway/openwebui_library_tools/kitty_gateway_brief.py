"""Open WebUI tool — pull current context brief from the Kitty gateway."""
import json

import requests

GATEWAY_URL = "http://127.0.0.1:8000"


class Tools:
    def get_brief(self) -> str:
        """Get Jacob's current context: active task, recent patterns, what he's working on."""
        try:
            resp = requests.get(f"{GATEWAY_URL}/brief", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                brief = data.get("brief") or data.get("content") or json.dumps(data, indent=2)
                return f"**Current Context Brief:**\n\n{brief}"
            return f"Gateway returned {resp.status_code}."
        except Exception as exc:
            return f"Brief unavailable: {exc}"
