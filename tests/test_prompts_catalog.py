"""Tests for gateway.prompts_catalog — the prompt-template catalog substrate.

The route layer was slimmed in Phase 3 to a thin wrapper. These
tests pin the substrate: the catalog is the canonical list, the
category filter is deterministic, and lookups by id are precise.
"""

from __future__ import annotations

from gateway import prompts_catalog


class TestListTemplates:
    def test_returns_all_when_no_filter(self) -> None:
        rows = prompts_catalog.list_templates()
        assert isinstance(rows, list)
        assert len(rows) >= 5
        ids = {r["id"] for r in rows}
        assert {"brainstorm", "debug", "summarize", "rewrite", "explain"} <= ids

    def test_returns_a_copy(self) -> None:
        """Mutating the returned list must not poison the catalog."""
        rows = prompts_catalog.list_templates()
        rows.clear()
        assert len(prompts_catalog.list_templates()) >= 5

    def test_each_template_has_required_fields(self) -> None:
        for row in prompts_catalog.list_templates():
            assert {"id", "title", "content", "category", "icon"} <= row.keys(), row

    def test_filter_by_category_case_insensitive(self) -> None:
        technical = prompts_catalog.list_templates(category="Technical")
        assert {r["id"] for r in technical} == {"debug"}
        technical2 = prompts_catalog.list_templates(category="technical")
        assert {r["id"] for r in technical2} == {"debug"}

    def test_unknown_category_yields_empty(self) -> None:
        assert prompts_catalog.list_templates(category="Cooking") == []

    def test_empty_string_filter_returns_all(self) -> None:
        assert len(prompts_catalog.list_templates(category="")) == len(
            prompts_catalog.list_templates()
        )


class TestGetTemplate:
    def test_returns_dict_for_known_id(self) -> None:
        template = prompts_catalog.get_template("debug")
        assert template is not None
        assert template["title"] == "Debug Code"
        assert "[code]" in template["content"]

    def test_returns_none_for_unknown_id(self) -> None:
        assert prompts_catalog.get_template("nonexistent") is None

    def test_returns_a_copy(self) -> None:
        first = prompts_catalog.get_template("brainstorm")
        assert first is not None
        first["title"] = "tampered"
        second = prompts_catalog.get_template("brainstorm")
        assert second is not None
        assert second["title"] == "Brainstorm"
