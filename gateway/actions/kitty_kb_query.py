"""
title: Kitty KB Query
author: kitty
version: 0.1
type: action
"""


import httpx


class Action:
    class Valves:
        pass

    class UserValves:
        pass

    def __init__(self):
        pass

    async def action(self, body: dict, __event_emitter__=None, __user__=None) -> dict:
        if __event_emitter__:
            await __event_emitter__({
                "type": "status",
                "data": {"description": "Searching knowledge base...", "done": False},
            })

        messages = body.get("messages", [])
        query = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                query = msg.get("content", "")
                break

        if not query:
            result = "Tell me what you want to search for."
        else:
            try:
                async with httpx.AsyncClient(timeout=15) as client:
                    resp = await client.get(
                        "http://127.0.0.1:8000/search",
                        params={"q": query, "limit": 5},
                    )
                if resp.status_code != 200:
                    result = f"Search failed (HTTP {resp.status_code})"
                else:
                    data = resp.json()
                    result = _format_results(data, query)
            except Exception as e:
                result = f"Search error: {e}"

        if __event_emitter__:
            await __event_emitter__({
                "type": "status",
                "data": {"description": "Knowledge search complete", "done": True},
            })
            await __event_emitter__({
                "type": "replace",
                "data": {"content": result},
            })

        return body


def _format_results(data: dict, query: str) -> str:
    sections = {
        "knowledge": "Knowledge",
        "memories": "Memories",
        "journal": "Journal",
    }
    total = 0
    lines = [f"**Knowledge Search: _{query}_**", ""]

    for section_key, section_label in sections.items():
        items = data.get(section_key, [])
        if not items:
            continue
        lines.append(f"### {section_label}")
        for i, item in enumerate(items[:3], 1):
            text = item.get("text", "")
            source = item.get("source", "?")
            title = item.get("title", source)
            if len(text) > 300:
                text = text[:300] + "..."
            lines.append(f"{i}. **{title}** — {text}")
            lines.append(f"   _Source: {source}_")
            lines.append("")
            total += 1

    if total == 0:
        lines.append("No results found.")

    lines.append(f"_{total} result(s)_")
    return "\n".join(lines)
