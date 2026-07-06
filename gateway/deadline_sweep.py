"""Urgent-thing sweep — discover deadlines across sources and push a report (P7, docs/packets/017).

Public API:
  sweep(*, push_fn=None, llm_fn=None, now=None) -> dict
"""
from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime
from typing import Any, Callable

from gateway import deadline_extractor, deadline_store, knowledge, signal_store

logger = logging.getLogger("kitty.deadline_sweep")

LlmFn = Callable[[str, str, str | None], str]
PushFn = Callable[..., bool]


def _default_push(message: str, *, title: str, kind: str, dedupe_key: str) -> bool:
    from gateway.push import push_to_jacob

    return push_to_jacob(message, title=title, kind=kind, dedupe_key=dedupe_key)


def _run_async(coro):
    """Run a coroutine from a sync context. Same seam as gateway/brief.py."""
    return asyncio.run(coro)


def _days_until(due_date_str: str, today: date) -> int:
    try:
        due = datetime.strptime(due_date_str, "%Y-%m-%d").date()
    except ValueError:
        return 9999
    return (due - today).days


def _score(deadline: dict[str, Any], today: date) -> float:
    """Rank by nearness × stakes. Higher is more urgent."""
    days = _days_until(deadline["due_date"], today)
    if days < 0:
        days = 0
    proximity = 1.0 / (1 + days)

    amount_weight = 1.0
    if deadline.get("amount"):
        amount_weight = 2.0

    confidence_weight = {"high": 1.5, "medium": 1.2, "low": 1.0, "needs_jacob": 1.0}.get(
        deadline.get("confidence", "needs_jacob"), 1.0
    )

    return proximity * amount_weight * confidence_weight


def _scan_documents(
    llm_fn: LlmFn | None, project_id: int
) -> tuple[list[dict[str, Any]], list[str]]:
    """Scan knowledge base for admin/benefits documents and extract deadlines."""
    found: list[dict[str, Any]] = []
    blind_spots: list[str] = []

    try:
        inventory = knowledge.get_inventory()
    except Exception as exc:
        logger.warning("knowledge inventory failed: %s", exc)
        blind_spots.append("knowledge base unavailable")
        return found, blind_spots

    if not inventory:
        blind_spots.append("no ingested documents")
        return found, blind_spots

    for source_name in inventory:
        try:
            chunks = _run_async(
                knowledge.search(
                    query="deadline due date obligation amount",
                    limit=5,
                    collections=None,
                    stitch_context=False,
                )
            )
        except Exception as exc:
            logger.warning("knowledge search failed for %s: %s", source_name, exc)
            continue

        text_parts: list[str] = []
        for chunk in chunks:
            meta = chunk.get("metadata") or {}
            doc_type = meta.get("doc_type", "general")
            collection = meta.get("collection", "general")
            if doc_type in {"letter", "form", "statement", "bill"} or collection == "benefits":
                text_parts.append(str(chunk.get("text", "")))

        if not text_parts:
            continue

        text = "\n\n".join(text_parts)
        try:
            extracted = deadline_extractor.extract_from_document(
                source=f"knowledge:{source_name}", text=text, llm_fn=llm_fn
            )
        except deadline_extractor.DeadlineExtractorError as exc:
            logger.warning("extraction failed for %s: %s", source_name, exc)
            extracted = []

        for item in extracted:
            item["project_id"] = project_id
            found.append(deadline_store.upsert(item))

    return found, blind_spots


def _scan_mail_signals(
    llm_fn: LlmFn | None, project_id: int
) -> tuple[list[dict[str, Any]], list[str]]:
    """Scan recent mail signals and extract deadlines."""
    found: list[dict[str, Any]] = []
    blind_spots: list[str] = []

    try:
        signals = signal_store.list_recent(limit=200, source="mail")
    except Exception as exc:
        logger.warning("signal list failed: %s", exc)
        blind_spots.append("mail signals unavailable")
        return found, blind_spots

    if not signals:
        blind_spots.append("no recent mail signals")

    for signal in signals:
        try:
            extracted = deadline_extractor.extract_from_mail_signal(signal, llm_fn=llm_fn)
        except deadline_extractor.DeadlineExtractorError as exc:
            logger.warning("extraction failed for signal %s: %s", signal.get("id"), exc)
            extracted = []
        for item in extracted:
            item["project_id"] = project_id
            found.append(deadline_store.upsert(item))

    return found, blind_spots


def sweep(
    *,
    push_fn: PushFn | None = None,
    llm_fn: LlmFn | None = None,
    now: date | None = None,
    project_id: int = 2,
) -> dict[str, Any]:
    """Run the urgent-thing sweep and optionally push a summary."""
    today = now if now is not None else date.today()

    doc_deadlines, doc_blind = _scan_documents(llm_fn, project_id)
    mail_deadlines, mail_blind = _scan_mail_signals(llm_fn, project_id)

    all_open = deadline_store.list_open(status="open")
    all_needs_jacob = deadline_store.list_needs_jacob()

    blind_spots = list(dict.fromkeys(doc_blind + mail_blind))

    if not all_open and not all_needs_jacob:
        blind_spots.append("no deadlines found in any scanned source")

    ranked = sorted(all_open, key=lambda d: _score(d, today), reverse=True)
    top = ranked[0] if ranked else None

    report = {
        "found": len(all_open) + len(all_needs_jacob),
        "open": len(all_open),
        "needs_jacob": len(all_needs_jacob),
        "top": top,
        "blind_spots": blind_spots,
        "generated_at": datetime.now().isoformat(),
    }

    if push_fn is not None:
        summary = _format_summary(report, today)
        dedupe_key = f"sweep-{today.isoformat()}"
        try:
            push_fn(summary, title="Urgent-thing sweep", kind="alert", dedupe_key=dedupe_key)
        except Exception as exc:  # noqa: BLE001
            logger.error("sweep push failed: %s", exc)

    return report


def _format_summary(report: dict[str, Any], today: date) -> str:
    lines = [f"Urgent-thing sweep for {today.isoformat()}"]
    if report.get("top"):
        top = report["top"]
        lines.append(f"Top: {top['obligation']} — due {top['due_date']}")
    lines.append(f"Open deadlines: {report['open']}; needs Jacob: {report['needs_jacob']}")
    if report.get("blind_spots"):
        lines.append("Blind spots: " + ", ".join(report["blind_spots"]))
    return "\n".join(lines)
