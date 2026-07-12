"""Tests for packet 024 — chat-log idea mine.

Covers the offline extractor (phase 1) and the review store / pipeline gate
(phase 2), and asserts packet 023 taste rules: no unreviewed item becomes
always-on memory, sensitive material stays quiet, and rejected / keep_quiet
items never surface.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gateway import idea_mine_store as store
from scripts.curation import extract_chat_goldmine as mine

FIXTURES = Path(__file__).parent / "fixtures"
SAMPLE_TRANSCRIPT = FIXTURES / "chat_goldmine_sample.json"


# ── Fake LLM that returns a hand-built extraction (the 7-item spec scenario) ──

def _canned_llm_response() -> str:
    return json.dumps(
        {
            "items": [
                {
                    "object_type": "project_thread",
                    "title": "Kitty as attention-repair assistant",
                    "sensitivity": "normal",
                    "one_line": "Kitty holds the thread: what mattered, what was decided, next move.",
                    "status": "active",
                    "domain": "kitty",
                    "why_it_matters": "Connects memory, briefing, creative, navigation into one thesis.",
                    "last_known_state": "Packet 023 authored.",
                    "next_small_move": "Review packet 023 language.",
                    "evidence_quote": "I want Kitty to hold the thread: where I was, what matters.",
                },
                {
                    "object_type": "project_thread",
                    "title": "Morning brief rebuild",
                    "sensitivity": "normal",
                    "one_line": "Rebuild the morning brief around continuity cards.",
                    "status": "parked",
                    "domain": "kitty",
                    "why_it_matters": "Morning is the highest-leverage surface.",
                    "last_known_state": "Half-scoped.",
                    "next_small_move": "Draft the Continue card.",
                    "evidence_quote": "Rebuild the morning brief around continuity cards.",
                },
                {
                    "object_type": "project_thread",
                    "title": "Vehicle maintenance tracker",
                    "sensitivity": "normal",
                    "one_line": "Track oil, tires, registration in one place.",
                    "status": "someday",
                    "domain": "vehicle",
                    "why_it_matters": "Avoids surprise breakdowns.",
                    "last_known_state": "Mentioned once.",
                    "next_small_move": "Collect the due dates.",
                    "evidence_quote": "Track oil, tires, registration in one place.",
                },
                {
                    "object_type": "preference_or_taste",
                    "title": "Continuity not surveillance",
                    "sensitivity": "normal",
                    "preference": "Memory should feel like continuity, not a case file.",
                    "applies_to": "Kitty memory, SOUL, context assembly",
                    "strength": "strong",
                    "avoid": "Defaulting to spirals/backstory.",
                    "examples": ["surface decisions before painful context"],
                    "evidence_quote": "Memory should feel like continuity, not surveillance.",
                },
                {
                    "object_type": "preference_or_taste",
                    "title": "Keep creative weirdness",
                    "sensitivity": "normal",
                    "preference": "Do not sanitize creative sparks into productivity notes.",
                    "applies_to": "creative mode",
                    "strength": "medium",
                    "avoid": "polishing away edge/humor",
                    "examples": ["preserve badly drawn cat motif"],
                    "evidence_quote": "Do not sanitize creative sparks into productivity notes.",
                },
                {
                    "object_type": "prompt_or_workflow",
                    "title": "Badly drawn cat image prompt",
                    "sensitivity": "normal",
                    "name": "mascot image prompt",
                    "purpose": "Generate the Kitty mascot consistently.",
                    "template": "badly drawn cat, imperfect warmth, recovery without branding it recovery",
                    "when_to_use": "any mascot image generation",
                    "inputs_needed": "motif, palette",
                    "output_expected": "image in the established style",
                    "evidence_quote": "badly drawn cat, imperfect warmth, recovery without branding it recovery",
                },
                {
                    "object_type": "idea_seed",
                    "title": "Sensitive recovery thread",
                    "sensitivity": "normal",
                    "spark": "therapy this week was hard, sobriety is the through-line but I keep spiraling at night",
                    "possible_use": "support preference, not identity memory",
                    "domain": "recovery_support",
                    "energy": "low",
                    "risk": "emotional",
                    "next_small_move": "one concrete next step, not a diagnosis",
                    "evidence_quote": "therapy this week was hard, sobriety is the through-line but I keep spiraling at night",
                },
            ]
        }
    )


def _fake_llm(messages: list[dict], model: str | None = None) -> str:
    return _canned_llm_response()


@pytest.fixture
def chunk():
    chunks = mine.load_source(SAMPLE_TRANSCRIPT)
    assert chunks, "fixture should yield at least one chunk"
    return chunks[0]


# ── Acceptance criterion 1: correct object types ──

def test_extractor_emits_correct_object_types(chunk):
    items = mine.extract_from_chunk(chunk, llm=_fake_llm)
    by_type = {}
    for it in items:
        by_type[it["object_type"]] = by_type.get(it["object_type"], 0) + 1
    assert by_type["project_thread"] == 3
    assert by_type["preference_or_taste"] == 2
    assert by_type["prompt_or_workflow"] == 1
    assert by_type["idea_seed"] == 1
    # every item carries the required tags
    for it in items:
        assert it["user_review"] == "unreviewed"
        assert "evidence_source" in it


# ── Acceptance criterion 2: sensitive recovery stays sensitive + unreviewed ──

def test_sensitive_recovery_marked_and_unreviewed(chunk):
    items = mine.extract_from_chunk(chunk, llm=_fake_llm)
    recovery = [i for i in items if i["title"] == "Sensitive recovery thread"][0]
    assert recovery["sensitivity"] in ("sensitive", "quiet")
    assert recovery["user_review"] == "unreviewed"


def test_tag_auto_bumps_sensitivity_on_hints():
    from scripts.curation.extract_chat_goldmine import Chunk, _tag

    chunk = Chunk(source="x.md", title="x", started_at=None, text="")
    item = {
        "object_type": "idea_seed",
        "sensitivity": "normal",
        "evidence_quote": "I mentioned my relapse and therapy session last night",
    }
    tagged = _tag(item, chunk)
    assert tagged["sensitivity"] == "sensitive"


# ── Acceptance criterion 3: extraction never writes to long-term memory ──

def test_extraction_writes_no_memory(chunk, tmp_path):
    items = mine.extract_from_chunk(chunk, llm=_fake_llm)
    # Pure transform: output items, no DB side effects claimed.
    assert isinstance(items, list) and items
    # Round-trip through the store uses the dedicated table only.
    db = tmp_path / "kitty.db"
    store.init_db(db_file=db)
    written = store.import_from_jsonl(
        _dump_jsonl(tmp_path, items), db_file=db
    )
    assert written == len(items)
    rows = store.list_items(db_file=db)
    assert all(r["user_review"] == "unreviewed" for r in rows)
    # Quarantined: nothing is surfaceable straight out of extraction.
    assert store.surfaceable_items(db_file=db) == []


# ── Acceptance criterion 4 + 7: review state gates surfacing ──

def _dump_jsonl(tmp_path: Path, items: list[dict]) -> Path:
    p = tmp_path / "items.jsonl"
    p.write_text("\n".join(json.dumps(i) for i in items), encoding="utf-8")
    return p


@pytest.fixture
def populated_store(tmp_path):
    db = tmp_path / "kitty.db"
    store.init_db(db_file=db)
    chunks = mine.load_source(SAMPLE_TRANSCRIPT)
    items = mine.extract_from_chunk(chunks[0], llm=_fake_llm)
    store.import_from_jsonl(_dump_jsonl(tmp_path, items), db_file=db)
    return db


def test_review_state_controls_surfacing(populated_store):
    rows = store.list_items(db_file=populated_store)
    assert len(rows) == 7
    # Before any review, nothing surfaces.
    assert store.surfaceable_items(db_file=populated_store) == []

    # Approve one project, edit one preference.
    project_id = next(r["id"] for r in rows if r["object_type"] == "project_thread")
    pref_id = next(r["id"] for r in rows if r["object_type"] == "preference_or_taste")
    assert store.set_review(project_id, "approved", db_file=populated_store)
    assert store.set_review(pref_id, "edited", db_file=populated_store)

    surfaced = store.surfaceable_items(db_file=populated_store)
    surfaced_ids = {r["id"] for r in surfaced}
    assert surfaced_ids == {project_id, pref_id}
    for r in surfaced:
        assert store.is_surfaceable(r)


def test_rejected_and_keep_quiet_never_surface(populated_store):
    rows = store.list_items(db_file=populated_store)
    reject_id = rows[0]["id"]
    quiet_id = rows[1]["id"]
    assert store.set_review(reject_id, "rejected", db_file=populated_store)
    assert store.set_review(quiet_id, "keep_quiet", db_file=populated_store)

    surfaced_ids = {r["id"] for r in store.surfaceable_items(db_file=populated_store)}
    assert reject_id not in surfaced_ids
    assert quiet_id not in surfaced_ids

    # The export hand-off must also skip them.
    exported = store.export_approved_to_inbox(
        db_file=populated_store, inbox_file=populated_store.with_suffix(".inbox.jsonl")
    )
    assert reject_id not in exported
    assert quiet_id not in exported
    assert exported == []  # nothing approved yet


# ── Acceptance criterion 5: parked / half-formed ideas survive ──

def test_parked_idea_survives(populated_store):
    rows = store.list_items(db_file=populated_store)
    parked = next(r for r in rows if r["payload"].get("status") == "parked")
    assert parked["payload"]["status"] == "parked"
    # It is retained (retrievable) even though not yet surfaceable.
    fetched = store.get_item(parked["id"], db_file=populated_store)
    assert fetched is not None
    assert fetched["payload"]["status"] == "parked"


# ── Acceptance criterion 6: creative weirdness preserved verbatim ──

def test_creative_weirdness_preserved(chunk, tmp_path):
    # Inject a genuinely weird creative spark and verify it survives import.
    weird = {
        "object_type": "idea_seed",
        "title": "a cat that is also a little lighthouse",
        "sensitivity": "normal",
        "spark": "what if the badly drawn cat sits on a cliff and is ALSO a tiny lighthouse made of warm regret",
        "possible_use": "mascot motif",
        "domain": "creative",
        "energy": "high",
        "risk": "none",
        "next_small_move": "sketch it badly",
        "evidence_quote": "what if the badly drawn cat sits on a cliff and is ALSO a tiny lighthouse",
    }
    db = tmp_path / "kitty.db"
    store.init_db(db_file=db)
    store.insert_item(weird, db_file=db)
    rows = store.list_items(db_file=db)
    assert rows[0]["payload"]["spark"] == weird["spark"]


# ── Loader exercises the chat-log fixture ──

def test_loader_reads_chatgpt_export():
    chunks = mine.load_source(SAMPLE_TRANSCRIPT)
    assert len(chunks) == 3
    titles = {c.title for c in chunks}
    assert "Recovery and staying sober" in titles
