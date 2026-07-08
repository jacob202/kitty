"""Packet 024 phase 1 — offline chat-log idea mine extractor.

Reads transcript files (ChatGPT `conversations.json` export, or plain
markdown / text of a single conversation) and produces a JSONL of
structured extraction candidates for later human review.

Nothing here writes to mem0, memory_graph, or the SQLite spine. The
output is a review file. Approval into always-on memory is out of scope
for phase 1 (packet 024 phases 2–3).

Privacy: cloud tier is refused. This is a local-first mine — recovery /
mental-health / grief material must never leak to a cloud model just
because the source transcript mentioned it.

Usage:
    python3 -m scripts.curation.extract_chat_goldmine \\
        --source path/to/conversations.json \\
        --out data/imports/chat_goldmine/2026-07-07/items.jsonl

    python3 -m scripts.curation.extract_chat_goldmine \\
        --source path/to/thread.md --dry-run
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Callable, Iterable

# ponytail: import at call time so `--dry-run` works without a live gateway.


OBJECT_TYPES = {
    "project_thread",
    "idea_seed",
    "decision_recovered",
    "preference_or_taste",
    "prompt_or_workflow",
}
SENSITIVITIES = {"normal", "personal", "sensitive", "quiet"}
REVIEW_STATES = {"unreviewed", "approved", "edited", "rejected", "keep_quiet"}
# ponytail: single chunk cap — real threads > 60k chars will get truncated
# with a warning. Raise the cap or add a splitter when a real mine run needs it.
MAX_CHUNK_CHARS = 60_000

_SENSITIVE_HINTS = (
    "sober", "sobriety", "recovery", "relapse", "detox", "grief",
    "grieving", "self-harm", "suicide", "trauma", "psych", "therapy",
    "meds", "medication", "hospital", "od'd", "overdose", "aa meeting",
    "na meeting", "mental health",
)


@dataclass(frozen=True)
class Chunk:
    """One conversation-shaped unit ready for extraction."""

    source: str        # human-readable "conversations.json#0" / "thread.md"
    title: str | None
    started_at: str | None
    text: str


# ── Loaders ──────────────────────────────────────────────────────────────────

def load_source(path: Path) -> list[Chunk]:
    """Dispatch by suffix. Only handles what the packet actually needs."""
    if path.suffix == ".json":
        return list(_load_chatgpt_export(path))
    if path.suffix in {".md", ".txt"}:
        return [_load_flat_text(path)]
    raise SystemExit(f"unsupported source: {path.suffix} (want .json, .md, .txt)")


def _load_chatgpt_export(path: Path) -> Iterable[Chunk]:
    """Yield one Chunk per ChatGPT conversation from a `conversations.json`."""
    data = json.loads(path.read_text())
    if not isinstance(data, list):
        raise SystemExit(f"{path}: expected top-level list of conversations")
    for idx, conv in enumerate(data):
        text = _flatten_chatgpt_messages(conv.get("mapping", {}))
        if not text.strip():
            continue
        yield Chunk(
            source=f"{path.name}#{idx}",
            title=conv.get("title"),
            started_at=_epoch_to_iso(conv.get("create_time")),
            text=text,
        )


def _load_flat_text(path: Path) -> Chunk:
    return Chunk(
        source=path.name,
        title=path.stem.replace("-", " ").replace("_", " "),
        started_at=None,
        text=path.read_text(),
    )


def _flatten_chatgpt_messages(mapping: dict) -> str:
    """Walk ChatGPT's node graph in create_time order into "role: text" lines."""
    turns: list[tuple[float, str, str]] = []
    for node in mapping.values():
        msg = node.get("message")
        if not msg:
            continue
        role = (msg.get("author") or {}).get("role", "?")
        parts = (msg.get("content") or {}).get("parts") or []
        text = "\n".join(p for p in parts if isinstance(p, str)).strip()
        if not text:
            continue
        turns.append((msg.get("create_time") or 0, role, text))
    turns.sort(key=lambda t: t[0])
    return "\n\n".join(f"{role}: {text}" for _, role, text in turns)


def _epoch_to_iso(epoch: float | int | None) -> str | None:
    if not epoch:
        return None
    return datetime.fromtimestamp(float(epoch), tz=timezone.utc).date().isoformat()


# ── Extraction ───────────────────────────────────────────────────────────────

EXTRACTION_INSTRUCTIONS = """You are mining one chat transcript for useful continuity threads for Jacob.

Return STRICT JSON: {"items": [ ... ]}. Each item MUST have:
  object_type: one of project_thread | idea_seed | decision_recovered | preference_or_taste | prompt_or_workflow
  title: short label
  sensitivity: normal | personal | sensitive | quiet
  user_review: always "unreviewed"
  evidence_quote: 1-2 short sentences copied verbatim from the transcript
  evidence_source: leave blank; the caller fills it

Plus fields per type:
  project_thread: one_line, status(active|parked|someday|stale|done|unknown), domain, why_it_matters, last_known_state, next_small_move
  idea_seed: spark, possible_use, domain, energy(high|medium|low|unknown), risk(rabbit_hole|money|emotional|technical|none), next_small_move
  decision_recovered: decision, context, why, date_or_period, applies_to, reopen_condition
  preference_or_taste: preference, applies_to, strength(strong|medium|weak|experimental), avoid, examples
  prompt_or_workflow: name, purpose, template, when_to_use, inputs_needed, output_expected

Rules:
- Extract useful continuity, not every fact. Prefer projects, decisions, prompts, workflows, taste, constraints.
- Recovery / mental health / grief / medical → sensitivity="sensitive" or "quiet". Do NOT invent psych labels.
- Keep creative sparks weird. Do not sanitize them into productivity notes.
- No item may be marked user_review other than "unreviewed".
- If the transcript has nothing worth mining, return {"items": []}.
"""


def extract_from_chunk(
    chunk: Chunk,
    *,
    llm: Callable[[list[dict], str], str],
    model: str | None = None,
) -> list[dict]:
    """Ask the LLM for structured items, tag each with evidence + source."""
    if len(chunk.text) > MAX_CHUNK_CHARS:
        sys.stderr.write(
            f"warn: {chunk.source} truncated from {len(chunk.text)} to {MAX_CHUNK_CHARS} chars\n"
        )
    text = chunk.text[:MAX_CHUNK_CHARS]
    messages = [
        {"role": "system", "content": EXTRACTION_INSTRUCTIONS},
        {
            "role": "user",
            "content": f"Transcript title: {chunk.title or '(none)'}\n\n{text}",
        },
    ]
    raw = llm(messages, model or "kitty-default")
    items = _parse_items(raw)
    return [_tag(item, chunk) for item in items if _valid(item)]


def _parse_items(raw: str) -> list[dict]:
    """Accept plain JSON or JSON inside a ```json fence."""
    stripped = raw.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*\})\s*```", stripped, re.DOTALL)
    if fence:
        stripped = fence.group(1)
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError as err:
        raise ExtractionParseError(f"LLM did not return JSON: {err}\n---\n{raw[:400]}") from err
    items = payload.get("items")
    if not isinstance(items, list):
        raise ExtractionParseError(f"LLM response missing 'items' list: {raw[:400]}")
    return items


def _valid(item: object) -> bool:
    """Drop items with a bad object_type or a review state we didn't ask for.

    Sensitivity default lands as 'normal' if the model omitted it.
    """
    if not isinstance(item, dict):
        return False
    if item.get("object_type") not in OBJECT_TYPES:
        return False
    if item.get("user_review", "unreviewed") != "unreviewed":
        return False
    return True


def _tag(item: dict, chunk: Chunk) -> dict:
    """Fill non-model fields; auto-bump sensitivity if hints slipped through."""
    tagged = dict(item)
    tagged.setdefault("user_review", "unreviewed")
    tagged.setdefault("sensitivity", "normal")
    if tagged["sensitivity"] not in SENSITIVITIES:
        tagged["sensitivity"] = "normal"
    quote = str(tagged.get("evidence_quote", "")).lower()
    if any(hint in quote for hint in _SENSITIVE_HINTS) and tagged["sensitivity"] == "normal":
        tagged["sensitivity"] = "sensitive"
    tagged["evidence_source"] = chunk.source
    if chunk.started_at:
        tagged.setdefault("date_or_period", chunk.started_at)
    return tagged


class ExtractionParseError(RuntimeError):
    pass


# ── LLM adapter ──────────────────────────────────────────────────────────────

def _gateway_llm(privacy_tier: str) -> Callable[[list[dict], str], str]:
    """Return a callable that hits the gateway's LLM hub with strict-JSON format."""
    if privacy_tier != "local":
        raise SystemExit(
            "refusing non-local privacy tier. transcripts may contain "
            "sensitive personal material; keep the mine local."
        )
    from gateway.llm_client import call_llm  # noqa: PLC0415  # local so --dry-run works standalone

    def _call(messages: list[dict], model: str) -> str:
        return call_llm(
            messages,
            model=model,
            temperature=0.2,
            max_tokens=3000,
            response_format={"type": "json_object"},
            operation="idea_mine.extract",
            privacy_tier="local",
            content_class="journal",
        )

    return _call


# ── CLI ──────────────────────────────────────────────────────────────────────

def _default_out_path() -> Path:
    stamp = date.today().isoformat()
    return Path("data/imports/chat_goldmine") / stamp / "items.jsonl"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--source", required=True, type=Path)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--model", default=None)
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="print chunk previews, do not call the LLM or write output",
    )
    args = ap.parse_args(argv)

    if not args.source.exists():
        sys.stderr.write(f"source not found: {args.source}\n")
        return 2

    chunks = load_source(args.source)
    if not chunks:
        sys.stderr.write(f"no non-empty conversations in {args.source}\n")
        return 1

    if args.dry_run:
        for c in chunks:
            print(f"{c.source} :: {c.title or '(untitled)'} :: {len(c.text)} chars")
        return 0

    llm = _gateway_llm(privacy_tier="local")
    out_path = args.out or _default_out_path()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    total = 0
    with out_path.open("w") as fh:
        for c in chunks:
            items = extract_from_chunk(c, llm=llm, model=args.model)
            for item in items:
                fh.write(json.dumps(item) + "\n")
                total += 1
            sys.stderr.write(f"{c.source}: {len(items)} item(s)\n")

    print(f"wrote {total} item(s) to {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
