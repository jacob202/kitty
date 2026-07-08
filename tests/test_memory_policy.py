"""Tests for the memory policy layer — classification, surfacing, rewriting."""

from datetime import datetime, timezone

from gateway.memory_graph import Item, Source
from gateway.memory_policy import (
    MemoryClass,
    classify,
    memory_display_reason,
    rewrite_sensitive_summary,
    should_surface,
)


def _item(
    text: str,
    source: Source = Source.MEMORY,
    tags: list[str] | None = None,
    **metadata,
) -> Item:
    m = dict(metadata)
    if tags is not None:
        m["tags"] = tags
    return Item(text=text, source=source, metadata=m)


# ── classify ──────────────────────────────────────────────────────────────────


class TestClassify:
    def test_pinned_from_metadata(self):
        item = _item("some fact", pinned=True)
        assert classify(item) == MemoryClass.PINNED

    def test_pinned_from_tag(self):
        item = _item("some fact", tags=["pinned"])
        assert classify(item) == MemoryClass.PINNED

    def test_blocked_from_metadata(self):
        item = _item("some fact", blocked=True)
        assert classify(item) == MemoryClass.BLOCKED

    def test_blocked_from_tag(self):
        item = _item("some fact", tags=["keep_quiet"])
        assert classify(item) == MemoryClass.BLOCKED

    def test_archived_from_metadata(self):
        item = _item("old fact", archived=True)
        assert classify(item) == MemoryClass.ARCHIVED

    def test_sensitive_from_high_sensitivity(self):
        item = _item("a check-in", sensitivity="high")
        assert classify(item) == MemoryClass.SENSITIVE_SUPPORT

    def test_sensitive_from_keywords(self):
        item = _item("recovery is going well today")
        assert classify(item) == MemoryClass.SENSITIVE_SUPPORT

    def test_sensitive_keyword_relapse(self):
        item = _item("worried about relapse")
        assert classify(item) == MemoryClass.SENSITIVE_SUPPORT

    def test_sensitive_keyword_grief(self):
        item = _item("dealing with grief")
        assert classify(item) == MemoryClass.SENSITIVE_SUPPORT

    def test_creative_thread_from_journal(self):
        item = _item("working on a poem about attention", source=Source.JOURNAL)
        assert classify(item) == MemoryClass.CREATIVE_THREAD

    def test_working_context_from_keywords(self):
        item = _item("decided to use FastAPI for the new service")
        assert classify(item) == MemoryClass.WORKING_CONTEXT

    def test_working_context_next_step(self):
        item = _item("next step is to deploy the migration")
        assert classify(item) == MemoryClass.WORKING_CONTEXT

    def test_preference_from_keywords(self):
        item = _item("i prefer dark mode")
        assert classify(item) == MemoryClass.PREFERENCE

    def test_preference_is_default_fallback(self):
        item = _item("the sky is blue")
        assert classify(item) == MemoryClass.PREFERENCE

    def test_creative_thread_from_other_sources(self):
        item = _item("writing a short story about a cat", source=Source.TRACES)
        assert classify(item) == MemoryClass.CREATIVE_THREAD

    def test_creative_keyword_painting(self):
        item = _item("started a new painting", source=Source.MEMORY)
        assert classify(item) == MemoryClass.CREATIVE_THREAD

    def test_working_context_implementing(self):
        item = _item("implementing the memory policy module")
        assert classify(item) == MemoryClass.WORKING_CONTEXT


# ── should_surface ────────────────────────────────────────────────────────────


class TestShouldSurface:
    def test_pinned_always_surfaces(self):
        item = _item("pinned fact", pinned=True)
        assert should_surface(item) is True

    def test_pinned_surfaces_with_query(self):
        item = _item("pinned fact", pinned=True)
        assert should_surface(item, query="something else") is True

    def test_blocked_never_surfaces(self):
        item = _item("blocked fact", blocked=True)
        assert should_surface(item) is False

    def test_blocked_keep_quiet(self):
        item = _item("quiet fact", tags=["keep_quiet"])
        assert should_surface(item) is False

    def test_archived_never_surfaces(self):
        item = _item("old stuff", archived=True)
        assert should_surface(item) is False

    def test_sensitive_support_suppressed_by_default(self):
        item = _item("recovery check-in")
        assert should_surface(item, query="how is the project going") is False

    def test_sensitive_support_surfaces_in_support_mode(self):
        item = _item("recovery check-in")
        assert should_surface(item, mode="support") is True

    def test_sensitive_support_surfaces_on_direct_query(self):
        item = _item("recovery check-in")
        assert should_surface(item, query="how is recovery going") is True

    def test_sensitive_support_therapy_query(self):
        item = _item("therapy session notes")
        assert should_surface(item, query="how was therapy") is True

    def test_working_context_surfaces_normally(self):
        item = _item("decided to use FastAPI")
        assert should_surface(item) is True

    def test_creative_thread_surfaces_normally(self):
        item = _item("poem about morning light", source=Source.JOURNAL)
        assert should_surface(item) is True

    def test_preference_surfaces_normally(self):
        item = _item("i prefer morning standups")
        assert should_surface(item) is True

    def test_default_surfaces_normally(self):
        item = _item("just a regular thought")
        assert should_surface(item) is True


# ── rewrite_sensitive_summary ────────────────────────────────────────────────


class TestRewriteSensitiveSummary:
    def test_spiraling_rewrite(self):
        result = rewrite_sensitive_summary("Jacob has been spiraling about work stress.")
        assert "prefers practical support" in result
        assert "spiraling" not in result

    def test_struggling_rewrite(self):
        result = rewrite_sensitive_summary("Jacob has been struggling with anxiety.")
        assert "prefers practical support" in result
        assert "struggling" not in result

    def test_recovery_focus_rewrite(self):
        result = rewrite_sensitive_summary("Jacob has been focused on recovery.")
        assert "practical and positive" in result
        assert "focused on recovery" not in result

    def test_keeps_struggling_rewrite(self):
        result = rewrite_sensitive_summary("Jacob keeps struggling with sleep.")
        assert "without making it the center" in result

    def test_dealing_with_rewrite(self):
        result = rewrite_sensitive_summary("Jacob has been dealing with grief.")
        assert "practical positivity" in result

    def test_going_through_rewrite(self):
        result = rewrite_sensitive_summary("Jacob has been going through a hard time.")
        assert "navigating" in result and "not dramatized" in result

    def test_catchall_recovery_rewrite(self):
        result = rewrite_sensitive_summary("Jacob has been thinking about recovery a lot.")
        assert "practical and positive" in result

    def test_benign_summary_unchanged(self):
        text = "Jacob has been building a new API gateway."
        result = rewrite_sensitive_summary(text)
        assert result == text

    def test_project_summary_unchanged(self):
        text = "Jacob has been implementing the frontend redesign."
        result = rewrite_sensitive_summary(text)
        assert result == text

    def test_decision_summary_unchanged(self):
        text = "Jacob decided to use SQLite for local storage."
        result = rewrite_sensitive_summary(text)
        assert result == text


# ── memory_display_reason ────────────────────────────────────────────────────


class TestMemoryDisplayReason:
    def test_pinned_reason(self):
        item = _item("fact", pinned=True)
        assert memory_display_reason(item) == "Pinned memory"

    def test_blocked_reason(self):
        item = _item("fact", blocked=True)
        assert memory_display_reason(item) == "Blocked"

    def test_working_context_reason(self):
        item = _item("decided to use Rust")
        assert memory_display_reason(item) == "Active project context"

    def test_preference_reason(self):
        item = _item("i prefer TDD")
        assert memory_display_reason(item) == "Preference"

    def test_creative_thread_reason(self):
        item = _item("poem about cats", source=Source.JOURNAL)
        assert memory_display_reason(item) == "Creative thread"

    def test_sensitive_support_reason(self):
        item = _item("recovery milestone")
        assert memory_display_reason(item) == "Support context"

    def test_default_fallback_reason(self):
        item = _item("something ordinary")
        assert memory_display_reason(item) == "Preference"
