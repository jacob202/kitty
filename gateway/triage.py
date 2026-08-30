"""Inbox triage (P2, docs/packets/002) — classify capture into action buckets.

For every inbox entry that has no ``inbox_triage`` row yet, ask an LLM which
bucket it belongs in, how confident it is, and why. A call below
``TRIAGE_CONFIDENCE_FLOOR`` is rerouted to ``needs_jacob`` rather than guessed.

Capture stays dumb (D4): triage never touches ``data/inbox.jsonl``. Results
live only in ``kitty.db``. ``drop`` is a bucket, not a deletion — a dropped
entry is still queryable.

There is no rule-based fallback. If the model is unavailable or returns output
this module cannot parse into a valid bucket, ``run_pass`` raises and writes
nothing for that entry (CLAUDE.md non-negotiable 1: fail loud, never guess).

Public API:
  run_pass(limit=25, llm_fn=None) -> dict
      Classify up to `limit` untriaged entries. Returns counts per bucket.
  list_triaged(bucket=None, limit=50) -> list[dict]
      Triage rows joined to their inbox entry text, newest first.
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any, Callable

from gateway import db as kitty_db
from gateway import desktop_store, user_context
from gateway.paths import CONFIG_DIR, KITTY_DB_FILE

logger = logging.getLogger("kitty.triage")

TRIAGE_DB_FILE = KITTY_DB_FILE
BUCKETS = ("now", "scheduled", "someday", "reference", "needs_jacob", "drop")
TRIAGE_CONFIDENCE_FLOOR = 0.6

# The route we ask for. call_llm may fall back to another provider, but the
# requested route is what we record; surfacing the actual provider would need
# call_llm to return it, which is out of scope for this packet.
_TRIAGE_ROUTE = "kitty-default"

# Injected callable: prompt -> raw model text. Parsing/validation is this
# module's job so the "unparseable output raises" path stays testable.
LlmFn = Callable[[str], str]


class TriageError(RuntimeError):
    """Raised when the model is unavailable or returns unusable output."""


def init_db() -> None:
    """Apply pending migrations. Idempotent."""
    kitty_db.migrate(db_file=TRIAGE_DB_FILE)


def run_pass(limit: int = 25, llm_fn: LlmFn | None = None) -> dict[str, Any]:
    """Classify up to `limit` untriaged inbox entries. Counts per bucket."""
    classify = llm_fn or _default_llm
    init_db()

    already = _triaged_ids()
    entries = [
        e
        for e in desktop_store.read_inbox(limit=0)
        if e.get("id") and e["id"] not in already
    ]
    pending = entries[:limit]

    counts = {bucket: 0 for bucket in BUCKETS}
    for entry in pending:
        result = _classify(entry, classify)
        _write_row(entry["id"], result)
        counts[result["bucket"]] += 1

    return {"processed": sum(counts.values()), "counts": counts}


def list_triaged(bucket: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    """Triage rows joined to inbox entry text, newest first. Optional bucket."""
    init_db()
    with kitty_db.connect(TRIAGE_DB_FILE) as conn:
        if bucket is None:
            rows = conn.execute(
                "SELECT inbox_id, ts, bucket, confidence, rationale, model "
                "FROM inbox_triage ORDER BY ts DESC, id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT inbox_id, ts, bucket, confidence, rationale, model "
                "FROM inbox_triage WHERE bucket = ? ORDER BY ts DESC, id DESC LIMIT ?",
                (bucket, limit),
            ).fetchall()

    entries = {e["id"]: e for e in desktop_store.read_inbox(limit=0) if e.get("id")}
    triaged: list[dict[str, Any]] = []
    for row in rows:
        entry = entries.get(row["inbox_id"])
        triaged.append(
            {
                "inbox_id": row["inbox_id"],
                "ts": row["ts"],
                "bucket": row["bucket"],
                "confidence": row["confidence"],
                "rationale": row["rationale"],
                "model": row["model"],
                "text": entry.get("text") if entry else None,
                "created_at": entry.get("created_at") if entry else None,
            }
        )
    return triaged


def _classify(entry: dict[str, Any], llm_fn: LlmFn) -> dict[str, Any]:
    """Ask the model, validate, apply the confidence floor. Raises on failure."""
    raw = llm_fn(_build_prompt(entry))
    if not raw or not raw.strip():
        raise TriageError(f"no model output for inbox entry {entry['id']}")

    data = _parse(raw, entry_id=entry["id"])
    bucket = data["bucket"]
    confidence = data["confidence"]
    rationale = data["rationale"]

    if bucket not in BUCKETS:
        raise TriageError(f"model returned unknown bucket {bucket!r} for {entry['id']}")

    if confidence < TRIAGE_CONFIDENCE_FLOOR and bucket != "needs_jacob":
        rationale = (
            f"confidence {confidence:.2f} below floor {TRIAGE_CONFIDENCE_FLOOR} — "
            f"rerouted from {bucket!r} to needs_jacob. Model said: {rationale}"
        )
        bucket = "needs_jacob"

    return {"bucket": bucket, "confidence": confidence, "rationale": rationale}


def _parse(raw: str, *, entry_id: str) -> dict[str, Any]:
    """Parse model JSON into validated fields. Raises TriageError on anything off."""
    text = raw.strip()
    if text.startswith("```"):
        # Strip a ```json ... ``` fence if the model added one despite the
        # JSON response format.
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise TriageError(
            f"unparseable triage output for {entry_id}: {exc}: {text[:200]}"
        ) from exc

    if not isinstance(data, dict):
        raise TriageError(f"triage output for {entry_id} is not a JSON object")

    for field in ("bucket", "confidence", "rationale"):
        if field not in data:
            raise TriageError(f"triage output for {entry_id} missing {field!r}")

    try:
        confidence = float(data["confidence"])
    except (TypeError, ValueError) as exc:
        raise TriageError(
            f"triage confidence for {entry_id} is not a number: {data['confidence']!r}"
        ) from exc

    return {
        "bucket": str(data["bucket"]).strip(),
        "confidence": confidence,
        "rationale": str(data["rationale"]).strip(),
    }


def _write_row(inbox_id: str, result: dict[str, Any]) -> None:
    with kitty_db.connect(TRIAGE_DB_FILE) as conn:
        conn.execute(
            "INSERT INTO inbox_triage (inbox_id, ts, bucket, confidence, rationale, model) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                inbox_id,
                time.time(),
                result["bucket"],
                result["confidence"],
                result["rationale"],
                _TRIAGE_ROUTE,
            ),
        )
        conn.commit()


def _triaged_ids() -> set[str]:
    init_db()
    with kitty_db.connect(TRIAGE_DB_FILE) as conn:
        return {row["inbox_id"] for row in conn.execute("SELECT inbox_id FROM inbox_triage")}


_SYSTEM_PROMPT = (
    "You are Kitty's inbox triage. For one captured note, decide which single "
    "bucket it belongs in and how sure you are.\n\n"
    "Buckets:\n"
    "- now: needs action today.\n"
    "- scheduled: has or needs a specific date/time.\n"
    "- someday: worth keeping, no deadline.\n"
    "- reference: information to keep, no action.\n"
    "- needs_jacob: genuinely ambiguous or high-stakes — Jacob must decide.\n"
    "- drop: noise, duplicate, or no longer relevant.\n\n"
    "Reply with ONLY a JSON object: "
    '{"bucket": "<one of the six>", "confidence": <0.0-1.0>, '
    '"rationale": "<one short sentence>"}. '
    "If you are not confident, say so with a low confidence number — do not guess."
)


def _default_llm(prompt: str) -> str:
    """Default classifier: Kitty's local route, JSON out, no creativity."""
    from gateway.llm_client import call_llm

    system = _SYSTEM_PROMPT
    context = user_context.load_user_context()
    prefs = _load_preferences()
    if context:
        system = f"{system}\n\n{context}"
    if prefs:
        system = f"{system}\n\n## Jacob's standing preferences\n\n{prefs}"

    return call_llm(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        model=_TRIAGE_ROUTE,
        max_tokens=300,
        temperature=0.0,
        response_format={"type": "json_object"},
        operation="inbox.triage",
    )


def _build_prompt(entry: dict[str, Any]) -> str:
    parts = [f"Captured note: {entry.get('text', '')}"]
    if entry.get("project"):
        parts.append(f"Project: {entry['project']}")
    if entry.get("tags"):
        parts.append(f"Tags: {', '.join(entry['tags'])}")
    if entry.get("created_at"):
        parts.append(f"Captured at: {entry['created_at']}")
    return "\n".join(parts)


def _load_preferences() -> str:
    path = CONFIG_DIR / "PREFERENCES.md"
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""
