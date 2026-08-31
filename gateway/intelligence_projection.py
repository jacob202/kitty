"""Read-only Home projection for the few things Kitty most wants to surface."""
from __future__ import annotations

from typing import Any, Callable

from gateway import deadline_store, insight_loop, life_awareness, magic_kitty


def _source(call: Callable[[], list[dict] | dict]) -> tuple[list[dict] | dict, dict[str, str | None]]:
    try:
        return call(), {"state": "available", "reason": None}
    except Exception as exc:
        return [], {"state": "unavailable", "reason": str(exc)}


def build_projection(limit: int = 3) -> dict[str, Any]:
    limit = max(1, min(int(limit), 5))
    candidates: list[dict[str, Any]] = []
    sources: dict[str, dict[str, str | None]] = {}

    deadlines, sources["deadline"] = _source(deadline_store.list_needs_jacob)
    for row in deadlines if isinstance(deadlines, list) else []:
        obligation = str(row.get("obligation") or "Deadline needs attention")
        project_id = row.get("project_id") if isinstance(row.get("project_id"), int) else None
        candidates.append({
            "id": f"deadline:{row.get('id')}", "source": "deadline", "score": 100.0,
            "title": obligation, "detail": f"Due {row.get('due_date') or 'soon'} · needs your confirmation",
            "destination": "projects" if project_id else "home", "project_id": project_id,
            "prompt": f"Help me handle this deadline: {obligation}",
        })

    due, sources["insight"] = _source(insight_loop.list_due)
    for row in due if isinstance(due, list) else []:
        payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
        text = str(payload.get("text") or "A saved thought is ready to revisit")
        category = str(payload.get("category") or "insight").replace("_", " ")
        candidates.append({
            "id": f"insight:{row.get('id')}", "source": "insight", "score": 90.0,
            "title": text, "detail": f"Returned {category}", "destination": "chat", "project_id": None,
            "prompt": f"Help me act on this returned insight: {text}",
        })

    magic, sources["magic"] = _source(magic_kitty.cached_connections)
    for row in magic if isinstance(magic, list) else []:
        confidence = row.get("confidence") if isinstance(row.get("confidence"), (int, float)) else 0.5
        title = str(row.get("title") or "Projects are connected")
        detail = str(row.get("detail") or row.get("source") or "Cross-project connection")
        candidates.append({
            "id": f"magic:{row.get('insight_id') or title}", "source": "magic",
            "score": 70.0 + max(0.0, min(float(confidence), 1.0)) * 20.0,
            "title": title, "detail": detail, "destination": "chat", "project_id": None,
            "prompt": f"Explore this cross-project connection with me: {title}. {detail}",
        })

    proactive, sources["life"] = _source(life_awareness.morning_proactive)
    suggestions = proactive.get("proactive_suggestions", []) if isinstance(proactive, dict) else []
    priority_score = {"high": 75.0, "medium": 55.0, "low": 35.0}
    for index, row in enumerate(suggestions if isinstance(suggestions, list) else []):
        if not isinstance(row, dict):
            continue
        text = str(row.get("text") or "Something worth doing today")
        project_id = row.get("project_id") if isinstance(row.get("project_id"), int) else None
        candidates.append({
            "id": f"life:{row.get('kind') or 'suggestion'}:{index}", "source": "life",
            "score": priority_score.get(str(row.get("priority") or "low"), 35.0),
            "title": text, "detail": str(row.get("why") or "From today's context"),
            "destination": "projects" if project_id else "home", "project_id": project_id,
            "prompt": f"Help me act on this: {text}",
        })

    candidates.sort(key=lambda item: (-float(item["score"]), str(item["id"])))
    items = [{key: value for key, value in item.items() if key != "score"} for item in candidates[:limit]]
    return {
        "items": items,
        "counts": {"shown": len(items), "total_candidates": len(candidates)},
        "sources": sources,
    }
