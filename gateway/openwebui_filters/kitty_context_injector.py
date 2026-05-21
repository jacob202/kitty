"""
title: Kitty Context Injector
author: kitty
author_url: https://github.com/jacobbrizinski/kitty
version: 0.2
"""

import logging
from typing import Optional

import httpx

logger = logging.getLogger("kitty.context_injector")

GATEWAY_URL = "http://127.0.0.1:8000"
MAX_SOURCE_LENGTH = 500


class Filter:
    class Valves:
        pass

    class UserValves:
        pass

    def __init__(self):
        self._sources: list[dict] = []

    def _search_body(self, messages: list) -> str | None:
        if not messages:
            return None
        for msg in reversed(messages):
            if msg.get("role") == "user":
                return msg.get("content") or None
        return None

    def _format_sources(self, data: dict) -> tuple[str, int]:
        sections = {
            "knowledge": "Knowledge",
            "memories": "Memories",
            "journal": "Journal",
        }
        lines = ["**Sources consulted:**\n"]
        total = 0
        for section_key, section_label in sections.items():
            items = data.get(section_key, [])
            if not items:
                continue
            lines.append(f"\n### {section_label}")
            for item in items:
                text = item.get("text", "")
                source = item.get("source", "?")
                title = item.get("title", source)
                if len(text) > MAX_SOURCE_LENGTH:
                    text = text[:MAX_SOURCE_LENGTH] + "..."
                lines.append(f"- **{title}**: {text}")
                self._sources.append(item)
                total += 1
        return "\n".join(lines), total

    async def _emit_status(self, __event_emitter__, action: str, query: str, done: bool):
        if __event_emitter__:
            await __event_emitter__({
                "type": "status",
                "data": {"action": action, "query": query, "done": done},
            })

    async def inlet(self, body: dict, __user__: Optional[dict] = None, __event_emitter__=None) -> dict:
        self._sources = []
        messages = body.get("messages", [])
        query = self._search_body(messages)
        if not query:
            return body

        await self._emit_status(__event_emitter__, "kitty_context_search", query, False)

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{GATEWAY_URL}/search",
                    params={"q": query, "limit": 5},
                )
            if resp.status_code != 200:
                logger.warning("Gateway search returned %d", resp.status_code)
                await self._emit_status(__event_emitter__, "kitty_context_search", query, True)
                return body
            data = resp.json()
        except Exception as e:
            logger.warning("Gateway search failed: %s", e)
            await self._emit_status(__event_emitter__, "kitty_context_search", query, True)
            return body

        context_block, total = self._format_sources(data)
        if total == 0:
            await self._emit_status(__event_emitter__, "kitty_context_search", query, True)
            return body

        last_user_idx = None
        for i in range(len(messages) - 1, -1, -1):
            if messages[i].get("role") == "user":
                last_user_idx = i
                break

        insert_at = (last_user_idx + 1) if last_user_idx is not None else len(messages)
        messages.insert(insert_at, {"role": "system", "content": context_block})
        body["messages"] = messages

        await self._emit_status(__event_emitter__, "kitty_context_search", query, True)
        return body

    async def outlet(self, body: dict, __user__: Optional[dict] = None, __event_emitter__=None) -> dict:
        if not self._sources:
            return body

        choices = body.get("choices", [])
        if not choices:
            return body

        content = choices[0].get("message", {}).get("content", "")
        if not content:
            return body

        cited = []
        for s in self._sources:
            title = s.get("title", "")
            source = s.get("source", "")
            label = title if title != source else source
            if label and label.lower() in content.lower():
                cited.append(f"- {title} ({source})")

        if not cited:
            return body

        citation_block = "\n\n---\n_Sources referenced:_\n" + "\n".join(cited)
        choices[0]["message"]["content"] = content + citation_block

        if __event_emitter__:
            await __event_emitter__({
                "type": "status",
                "data": {"description": f"Cited {len(cited)} sources in response", "done": True},
            })

        return body
