"""Deadline extraction from health/admin documents and mail signals (P7, docs/packets/017).

All extraction runs local-only (privacy_tier="local", content_class="health_admin")
to satisfy D10. Callers provide an injected `llm_fn` for tests; the default uses
the local model route via gateway.llm_client.

Public API:
  extract_from_text(text, *, source, source_id=None, llm_fn=None) -> list[dict]
  extract_from_document(source, text, *, llm_fn=None) -> list[dict]
  extract_from_mail_signal(signal, *, llm_fn=None) -> list[dict]
"""
from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Callable

from gateway import deadline_store

logger = logging.getLogger("kitty.deadline_extractor")

LlmFn = Callable[[str, str, str | None], str]

_SYSTEM_PROMPT = (
    "You extract deadlines, obligations, and amounts from administrative documents "
    "or mail summaries. Return ONLY a JSON array of objects. Each object has: "
    "due_date (YYYY-MM-DD or null if unclear), obligation (short text), "
    "amount (text or null), currency (text or null), "
    "confidence (high|medium|low|needs_jacob), notes (short text or empty). "
    "Use 'needs_jacob' when a date is mentioned but ambiguous or the obligation "
    "is unclear. Do not guess dates. Do not include explanatory text outside the JSON."
)

_DEFAULT_CONFIDENCE = "needs_jacob"


class DeadlineExtractorError(RuntimeError):
    """Raised when extraction fails in a way the caller should surface, not drop."""


def _default_llm(prompt: str, privacy_tier: str, content_class: str | None) -> str:
    from gateway.llm_client import call_llm

    return call_llm(
        [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        max_tokens=800,
        temperature=0.1,
        response_format={"type": "json_object"},
        operation="deadline.extract",
        privacy_tier=privacy_tier,
        content_class=content_class,
    )


def _make_dedupe_key(source: str, due_date: str, obligation: str) -> str:
    normalized = f"{source}|{due_date}|{obligation.strip().lower()}"
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:24]
    return f"deadline:{source.split(':')[0]}:{digest}"


def _sanitize_item(item: dict[str, Any], source: str, source_id: str | None) -> dict[str, Any] | None:
    """Normalize one extracted item and drop empty/unusable entries."""
    obligation = str(item.get("obligation") or "").strip()
    if not obligation:
        return None

    due_date = item.get("due_date")
    if due_date is None or str(due_date).lower() in {"null", "none", ""}:
        due_date = None
    else:
        due_date = str(due_date).strip()

    confidence = str(item.get("confidence", _DEFAULT_CONFIDENCE)).lower()
    if confidence not in {"high", "medium", "low"} or due_date is None:
        confidence = "needs_jacob"

    amount = item.get("amount")
    currency = item.get("currency")

    return {
        "source": source,
        "source_id": source_id,
        "due_date": due_date,
        "obligation": obligation,
        "amount": amount if amount not in (None, "null", "None") else None,
        "currency": currency if currency not in (None, "null", "None") else None,
        "confidence": confidence,
        "dedupe_key": _make_dedupe_key(source, due_date or "unknown", obligation),
    }


def _parse_llm_response(raw: str) -> list[dict[str, Any]]:
    """Parse the model response into a list of deadline dicts."""
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise DeadlineExtractorError(f"model response was not valid JSON: {raw[:200]!r}") from exc

    if isinstance(parsed, dict):
        if "deadlines" in parsed:
            parsed = parsed["deadlines"]
        elif "items" in parsed:
            parsed = parsed["items"]
        else:
            raise DeadlineExtractorError(f"expected JSON array of deadlines, got object with no deadlines/items: {raw[:200]!r}")
    if not isinstance(parsed, list):
        raise DeadlineExtractorError(f"expected JSON array of deadlines, got {type(parsed).__name__}: {raw[:200]!r}")

    return parsed


def extract_from_text(
    text: str,
    *,
    source: str,
    source_id: str | None = None,
    llm_fn: LlmFn | None = None,
) -> list[dict[str, Any]]:
    """Extract deadline tuples from raw text."""
    call = llm_fn or _default_llm
    if not text or not text.strip():
        return []

    prompt = (
        "Extract deadlines from the following administrative text. "
        "Return only the JSON array described in your instructions.\n\n"
        f"{text[:8000]}"
    )
    raw = call(prompt, "local", "health_admin")
    items = _parse_llm_response(raw)

    results: list[dict[str, Any]] = []
    for item in items:
        sanitized = _sanitize_item(item, source, source_id)
        if sanitized is not None:
            results.append(sanitized)
    return results


def extract_from_document(
    source: str,
    text: str,
    *,
    llm_fn: LlmFn | None = None,
) -> list[dict[str, Any]]:
    """Extract deadlines from an ingested document source."""
    return extract_from_text(text, source=source, source_id=None, llm_fn=llm_fn)


def extract_from_mail_signal(
    signal: dict[str, Any],
    *,
    llm_fn: LlmFn | None = None,
) -> list[dict[str, Any]]:
    """Extract deadlines from a mail signal payload."""
    if signal.get("source") != "mail":
        return []

    payload = signal.get("payload") or {}
    text = str(payload.get("summary") or payload.get("snippet") or "").strip()
    if not text:
        return []

    source_id = payload.get("message_id") or str(signal.get("id"))
    return extract_from_text(text, source="mail", source_id=source_id, llm_fn=llm_fn)


def extract_and_upsert(
    text: str,
    *,
    source: str,
    source_id: str | None = None,
    project_id: int,
    llm_fn: LlmFn | None = None,
) -> list[dict[str, Any]]:
    """Extract deadlines and upsert them into the store."""
    extracted = extract_from_text(text, source=source, source_id=source_id, llm_fn=llm_fn)
    stored: list[dict[str, Any]] = []
    for item in extracted:
        item["project_id"] = project_id
        stored.append(deadline_store.upsert(item))
    return stored
