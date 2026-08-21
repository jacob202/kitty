"""skill_registry.suggest() surfaces reasoning skills by their USE WHEN triggers."""
from gateway import skill_registry


def test_suggest_does_not_surface_archived_red_team():
    matches = skill_registry.suggest("help me find weaknesses and poke holes in this plan")
    assert all(match["name"] != "red-team" for match in matches)


def test_suggest_does_not_surface_archived_root_cause():
    matches = skill_registry.suggest("why does this keep failing every week")
    assert all(match["name"] != "root-cause-analysis" for match in matches)


def test_suggest_no_match_is_empty():
    assert skill_registry.suggest("hello there friend") == []


def test_suggest_empty_message():
    assert skill_registry.suggest("") == []


def test_triggers_are_multiword_only():
    # single-word noise must be filtered out
    for skill in skill_registry.discover():
        assert all(len(t.split()) >= 2 for t in skill_registry._triggers(skill))
