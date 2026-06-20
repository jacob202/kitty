"""Tests for ``gateway.prompts`` — the central catalog of inline prompts."""

from __future__ import annotations

import pytest

from gateway import prompts


def test_catalog_has_expected_names():
    names = {entry["name"] for entry in prompts.list_prompts()}
    assert "journal.interview" in names
    assert "journal.synthesis" in names
    assert "parts.council" in names
    assert "inventory.photo" in names


def test_every_catalog_entry_has_a_version_tag():
    for entry in prompts.list_prompts():
        assert entry["version"].startswith("v"), entry
        assert entry["chars"] > 0, entry


def test_get_prompt_returns_constant_value():
    assert prompts.get_prompt("journal.interview") == prompts.JOURNAL_INTERVIEW_PROMPT
    assert prompts.get_prompt("parts.council") == prompts.PARTS_COUNCIL_PROMPT


def test_get_prompt_raises_keyerror_for_unknown_name():
    with pytest.raises(KeyError):
        prompts.get_prompt("does.not.exist")


def test_get_prompt_version():
    assert prompts.get_prompt_version("journal.interview") == "v1"
    assert prompts.get_prompt_version("inventory.photo") == "v1"


def test_journal_prompts_mention_jacob():
    """Sanity check that the journal prompts aren't accidentally swapped."""
    assert "Jacob" in prompts.JOURNAL_INTERVIEW_PROMPT
    assert "Jacob" in prompts.JOURNAL_SYNTHESIS_PROMPT


def test_parts_prompt_contains_all_four_parts():
    for role in ("Skeptic", "Champion", "Pragmatist", "Observer"):
        assert role in prompts.PARTS_COUNCIL_PROMPT, role


def test_inventory_prompt_requires_json_output():
    assert "JSON" in prompts.INVENTORY_PHOTO_PROMPT
    assert "part_number" in prompts.INVENTORY_PHOTO_PROMPT
