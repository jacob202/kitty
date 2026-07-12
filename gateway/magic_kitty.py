"""Magic Kitty — cross-project insight discovery (DOCS ADR-0014 / packet 022).

Walks all active projects, composes their resume state, and feeds them
to an LLM to surface non-obvious connections between projects — the
"huh, these are actually related" moment.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Any

from gateway import llm_client, project_store
from gateway.project_resume import resume as project_resume

logger = logging.getLogger("kitty.magic_kitty")

_LAST_CONNECTIONS_CACHE: dict[str, Any] = {
    "connections": [],
    "generated_at": 0.0,
    "projects_used": 0,
}


def discover_connections(force: bool = False) -> dict[str, Any]:
    """Return cross-project connection insights.

    Caches results for 5 minutes unless ``force=True``.
    """
    now = time.time()
    cached = _LAST_CONNECTIONS_CACHE
    if not force and cached["generated_at"] > 0 and (now - cached["generated_at"]) < 300:
        return dict(cached)

    projects = project_store.list_projects(status="active")
    if not projects:
        projects = project_store.list_projects()

    resumes: list[dict[str, Any]] = []
    for p in projects:
        try:
            r = project_resume(p["id"])
            resumes.append(r)
        except Exception as exc:
            raise RuntimeError(
                f"magic_kitty failed to build resume for project {p['id']}: {exc}"
            ) from exc

    if len(resumes) < 2:
        cached["connections"] = []
        cached["generated_at"] = now
        cached["projects_used"] = len(resumes)
        return dict(cached)

    connections = _call_llm_for_connections(resumes)

    cached["connections"] = connections
    cached["generated_at"] = now
    cached["projects_used"] = len(resumes)
    return dict(cached)


_CONNECTION_PROMPT = """You are Magic Kitty, a cross-project insight engine.
Look at the following active project resumes and find non-obvious connections
between them. These should be real, useful insights — not generic observations.

For each connection, output a JSON object with:
- "insight_id": a short unique id
- "kind": one of "pattern", "anomaly", "suggestion", "milestone"
- "title": a punchy headline
- "detail": 1-2 sentence explanation
- "source": comma-separated project names involved
- "confidence": 0.0 to 1.0

Return a JSON array of connection objects. If there are no meaningful
connections, return an empty array.

Projects:
"""


def _call_llm_for_connections(resumes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    serialized = json.dumps(
        [
            {
                "name": r["name"],
                "kind": r["kind"],
                "summary": r["summary"],
                "open_questions": r["open_questions"],
            }
            for r in resumes
        ],
        indent=2,
    )
    messages = [
        {"role": "system", "content": _CONNECTION_PROMPT + serialized},
        {"role": "user", "content": "What connections do you see between these projects?"},
    ]
    try:
        text = llm_client.call_llm(
            messages,
            model="kitty-default",
            max_tokens=2000,
            temperature=0.4,
            operation="magic_kitty.discover",
            # D10: cross-project synthesis aggregates every active project,
            # including benefits-admin whose summary can hold health_admin
            # content. Fail toward privacy — local tier only, never cloud.
            privacy_tier="local",
            content_class="health_admin",
        )
        if not text:
            raise RuntimeError(
                "magic_kitty LLM returned empty response for operation magic_kitty.discover"
            )
        logger.info("magic_kitty raw LLM response (first 300 chars): %s", text[:300])
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1]
            cleaned = cleaned.rsplit("```", 1)[0].strip()
        if cleaned.startswith("```"):
            cleaned = cleaned[3:].strip()
        parsed = json.loads(cleaned)
        if isinstance(parsed, list):
            for c in parsed:
                if "insight_id" not in c:
                    c["insight_id"] = uuid.uuid4().hex[:8]
                c["created_at"] = time.time()
            return parsed
        raise TypeError(f"magic_kitty expected LLM JSON list, got {type(parsed).__name__}")
    except Exception as exc:
        raise RuntimeError(
            f"magic_kitty LLM call failed for operation magic_kitty.discover: {exc}"
        ) from exc
