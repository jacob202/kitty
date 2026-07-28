"""Provider preference: the switch Jacob asked for, and its guard rails."""

from __future__ import annotations

import json

import pytest

from gateway import provider_prefs

KNOWN = ("local", "openai", "nvidia", "agentrouter", "openrouter", "gemini")
DEFAULT = KNOWN


@pytest.fixture(autouse=True)
def prefs_file(tmp_path, monkeypatch):
    path = tmp_path / "providers.json"
    monkeypatch.setattr(provider_prefs, "PROVIDER_PREFS_FILE", path)
    return path


def test_no_preference_uses_default_order():
    assert provider_prefs.resolve_order(KNOWN, DEFAULT) == list(DEFAULT)


def test_saved_order_wins_and_the_rest_follow():
    provider_prefs.save_preferences(["openrouter", "local"], [], known=KNOWN)

    order = provider_prefs.resolve_order(KNOWN, DEFAULT)
    assert order[:2] == ["openrouter", "local"]
    assert set(order) == set(KNOWN)


def test_disabled_providers_leave_the_chain():
    provider_prefs.save_preferences([], ["openrouter", "agentrouter"], known=KNOWN)

    order = provider_prefs.resolve_order(KNOWN, DEFAULT)
    assert "openrouter" not in order
    assert "agentrouter" not in order
    assert "local" in order


def test_provider_dropped_from_the_table_falls_out_of_a_saved_order():
    provider_prefs.save_preferences(["openrouter", "local"], [], known=KNOWN)

    order = provider_prefs.resolve_order(("local", "openai"), ("local", "openai"))
    assert order == ["local", "openai"]


def test_provider_added_to_the_table_lands_at_the_end():
    provider_prefs.save_preferences(["openai"], [], known=KNOWN)

    order = provider_prefs.resolve_order((*KNOWN, "brandnew"), DEFAULT)
    assert order[0] == "openai"
    assert order[-1] == "brandnew"


def test_unknown_provider_is_rejected_not_silently_dropped():
    with pytest.raises(ValueError, match="unknown provider"):
        provider_prefs.save_preferences(["openrouterr"], [], known=KNOWN)


def test_duplicate_in_order_is_rejected():
    with pytest.raises(ValueError, match="duplicates"):
        provider_prefs.save_preferences(["local", "local"], [], known=KNOWN)


def test_disabling_every_provider_is_rejected():
    with pytest.raises(ValueError, match="nothing to call"):
        provider_prefs.save_preferences([], list(KNOWN), known=KNOWN)


def test_corrupt_preferences_do_not_break_routing(prefs_file):
    prefs_file.write_text("{not json")

    assert provider_prefs.resolve_order(KNOWN, DEFAULT) == list(DEFAULT)


def test_non_object_preferences_do_not_break_routing(prefs_file):
    prefs_file.write_text(json.dumps(["local"]))

    assert provider_prefs.resolve_order(KNOWN, DEFAULT) == list(DEFAULT)
