"""Kitty Tutor — RAG learning scaffold built on the existing knowledge pipeline.

Designed for zero-friction daily use:
  - Ingest a doc once:  kitty tutor learn <path>
  - Ask a question:     kitty tutor ask "what is refactoring"
  - Review weak spots:  kitty tutor review   /   kitty tutor rate "<term>" <1-3>

The Tutor NEVER guesses. With no docs on a topic it says so and tells you the
exact command to fix it. Answers are vocabulary-first, three sentences max, with
a plain analogy and one check-in question. State lives in SQLite so it remembers
what you struggle with and reviews it later — no effort from you.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Awaitable, Callable, Sequence

from gateway import knowledge
from gateway.paths import KITTY_DATA_DIR

logger = logging.getLogger("kitty.tutor")

# Reuses the same ChromaDB collection the rest of Kitty already indexes into.
TUTOR_COLLECTION = "tutor"
MEMORY_DB = KITTY_DATA_DIR / "tutor_memory.db"


class KnowledgeType(str, Enum):
    """Category of a learning term, driving its review cadence.

    Adapted from DeepTutor's four-type model
    (``deeptutor/learning/scheduler.py``): memory and procedure facts need
    tighter early review than concepts and designs. Each type maps a 1-3
    confidence score to a review delay in days.
    """

    MEMORY = "memory"
    CONCEPT = "concept"
    PROCEDURE = "procedure"
    DESIGN = "design"


# Review delay (days) per (knowledge type, confidence score).
# score 1 = got it, 2 = needs review, 3 = lost (due next session).
# MEMORY preserves the pre-existing {1: 3, 2: 1, 3: 0} behavior.
KNOWLEDGE_TYPE_INTERVALS: dict[KnowledgeType, dict[int, int]] = {
    KnowledgeType.MEMORY: {1: 3, 2: 1, 3: 0},
    KnowledgeType.CONCEPT: {1: 7, 2: 3, 3: 0},
    KnowledgeType.PROCEDURE: {1: 7, 2: 3, 3: 0},
    KnowledgeType.DESIGN: {1: 28, 2: 14, 3: 0},
}


class TutorError(Exception):
    """Raised when the Tutor cannot answer without guessing."""


async def ingest(path: str | Path, label: str | None = None) -> dict:
    """Ingest a document into the Tutor collection. One command, no flags."""
    return await knowledge.ingest(
        path, collection=TUTOR_COLLECTION, source_label=label, sensitivity="low"
    )


async def retrieve(topic: str, limit: int = 3) -> list[str]:
    """Pull the top chunks for a topic from the Tutor collection."""
    chunks = await knowledge.search(topic, collections=[TUTOR_COLLECTION], limit=limit)
    return [c["text"] for c in chunks if c.get("text")]


def _build_tutor_prompt(topic: str, chunks: Sequence[str]) -> list[dict]:
    context = "\n\n---\n\n".join(chunks)
    system = (
        "You are the Kitty Tutor. Teach one concept at a time.\n"
        "Rules you MUST follow:\n"
        "1. VOCABULARY FIRST: name the 3 most important technical terms, define each in one line.\n"
        "2. EXPLAIN in at most 3 sentences using a simple mechanical or construction analogy.\n"
        "3. END with exactly one short Socratic check-in question.\n"
        "4. ONLY use the documentation below. If the answer is not in it, output {\"none\": true}.\n"
        'Output strict JSON: {"vocab": [3 strings], "explain": string, "question": string}.\n'
        f"Topic: {topic}\n\nDocumentation:\n{context}"
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": f"Teach me: {topic}"},
    ]


def _parse(response: str, topic: str) -> dict:
    try:
        data = json.loads(response)
    except json.JSONDecodeError as exc:
        raise TutorError(f"Tutor produced non-JSON output for {topic!r}") from exc
    if data.get("none"):
        raise TutorError(
            f"I don't have documentation on '{topic}'. "
            f"Run: kitty tutor learn <path/to/doc>"
        )
    if not all(k in data for k in ("vocab", "explain", "question")):
        raise TutorError(f"Tutor response missing fields for {topic!r}")
    return data


async def ask(
    topic: str,
    *,
    retriever: Callable[[str], Awaitable[list[str]]] | None = None,
    llm: Callable[[list[dict]], str] | None = None,
) -> dict:
    """Answer a learning question. Vocab-first, grounded, no guessing."""
    retriever = retriever or retrieve
    llm = llm or _default_llm
    chunks = await retriever(topic)
    if not chunks:
        raise TutorError(
            f"I don't have documentation on '{topic}'. "
            f"Run: kitty tutor learn <path/to/doc>"
        )
    raw = llm(_build_tutor_prompt(topic, chunks))
    return _parse(raw, topic)


def _default_llm(messages: list[dict]) -> str:
    from gateway.llm_client import call_llm

    return call_llm(messages, max_tokens=600, temperature=0.3)


def _similarity(a: str, b: str) -> float:
    """Normalized Levenshtein similarity in [0, 1]."""
    a, b = a.lower().strip(), b.lower().strip()
    if a == b:
        return 1.0
    if not a or not b:
        return 0.0
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    distance = prev[-1]
    return 1.0 - distance / max(len(a), len(b))


def grade_answer(
    user_answer: str,
    expected_answer: str,
    question_type: str = "open",
) -> bool:
    """Deterministic grading — no LLM variance.

    Adapted from DeepTutor's ``deeptutor/learning/grading.py``:
      - choice: exact match (case/space-insensitive)
      - short:  exact match, or similarity >= 0.85 when <= 30 chars
      - open:   keyword-overlap ratio >= 0.6
    """
    user = user_answer.strip()
    expected = expected_answer.strip()
    if question_type == "choice":
        return user.lower() == expected.lower()
    if question_type == "short":
        if user.lower() == expected.lower():
            return True
        if len(user) <= 30:
            return _similarity(user, expected) >= 0.85
        return False
    # open-ended
    exp_words = {w for w in expected.lower().split() if len(w) > 2}
    if not exp_words:
        return user.lower() == expected.lower()
    user_words = set(user.lower().split())
    overlap = len(exp_words & user_words) / len(exp_words)
    return overlap >= 0.6


# ── Memory: confidence logging + spaced repetition ────────────────────────────


def _conn() -> sqlite3.Connection:
    MEMORY_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(MEMORY_DB)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS vocabulary_terms ("
        "term TEXT PRIMARY KEY, subject TEXT, last_score INTEGER, next_review TEXT)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS user_confidence_logs ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, term TEXT, score INTEGER, ts TEXT)"
    )
    return conn


def log_confidence(
    term: str,
    score: int,
    subject: str = "",
    knowledge_type: KnowledgeType = KnowledgeType.MEMORY,
) -> None:
    """Record a 1-3 confidence rating and schedule the next review.

    ``knowledge_type`` selects the review cadence. Defaults to MEMORY, which
    preserves the original fixed-interval behavior.
    """
    if score not in (1, 2, 3):
        raise TutorError("confidence score must be 1, 2, or 3")
    if not isinstance(knowledge_type, KnowledgeType):
        raise TutorError(f"knowledge_type must be a KnowledgeType, got {knowledge_type!r}")
    now = datetime.now(timezone.utc)
    days = KNOWLEDGE_TYPE_INTERVALS[knowledge_type][score]
    next_review = (now + timedelta(days=days)).isoformat()
    with _conn() as conn:
        conn.execute(
            "INSERT INTO user_confidence_logs (term, score, ts) VALUES (?,?,?)",
            (term, score, now.isoformat()),
        )
        conn.execute(
            "INSERT INTO vocabulary_terms (term, subject, last_score, next_review) "
            "VALUES (?,?,?,?) "
            "ON CONFLICT(term) DO UPDATE SET "
            "last_score=excluded.last_score, next_review=excluded.next_review",
            (term, subject, score, next_review),
        )


def due_review(now: datetime | None = None) -> list[dict]:
    """Terms whose next review is due (or lost). Empty list = nothing to do."""
    now = now or datetime.now(timezone.utc)
    with _conn() as conn:
        rows = conn.execute(
            "SELECT term, subject, last_score, next_review FROM vocabulary_terms "
            "WHERE next_review <= ? ORDER BY next_review",
            (now.isoformat(),),
        ).fetchall()
    return [
        {"term": r[0], "subject": r[1], "last_score": r[2], "next_review": r[3]}
        for r in rows
    ]
