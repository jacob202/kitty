"""Tests for the three self-review signals."""
from gateway.self_review import _classify_signal, log_drift, log_reaction


def test_drift_passes_clean_response():
    r = log_drift("I don't know, but let's figure it out.")
    assert r["pass"] is True
    assert r["violations"] == []


def test_drift_catches_certainly():
    r = log_drift("Certainly! I can help with that.")
    assert r["pass"] is False
    assert any("certainly" in v for v in r["violations"])


def test_drift_catches_great_question():
    r = log_drift("Great question! Here's what I think.")
    assert r["pass"] is False


def test_drift_catches_unearned_agreement():
    r = log_drift("You're absolutely right, that makes total sense.")
    assert r["pass"] is False


def test_reaction_correction_signal():
    assert _classify_signal("No, that's wrong — the answer is X") == "correction"


def test_reaction_short_signal():
    assert _classify_signal("ok") == "short"


def test_reaction_deep_engagement():
    long_msg = "Actually I've been thinking about this a lot and here's my take: " + "x" * 200
    assert _classify_signal(long_msg) == "deep_engagement"


def test_reaction_redirect():
    assert _classify_signal("Anyway, different question entirely") == "redirect"


def test_log_reaction_returns_record():
    r = log_reaction("yeah makes sense", prev_kitty_length=150)
    assert "signal" in r
    assert r["prev_kitty_length"] == 150
