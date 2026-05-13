"""Tests for voice_gate — SOUL.md compliance filtering before response delivery."""
import pytest
from gateway.voice_gate import (
    check,
    filter_response,
    VoiceGateResult,
    get_drift_nudge,
    record_drift,
    reset_drift_counter,
)


class TestCheck:
    def test_clean_response_passes(self):
        result = check("Yeah, that bias supply was acting up.")
        assert result.passed
        assert result.violations == []
        assert result.cleaned == result.original

    def test_banned_phrase_detected(self):
        result = check("Certainly! Let me help you with that.")
        assert not result.passed
        assert any("certainly" in v for v in result.violations)

    def test_unearned_agreement_detected(self):
        result = check("You're absolutely right, that's the way to go.")
        assert not result.passed
        assert any("unearned_agreement" in v for v in result.violations)

    def test_hedge_detected(self):
        result = check("I apologize for the confusion, some might say otherwise.")
        assert not result.passed
        assert len(result.violations) >= 1

    def test_multiple_violations_escalates_severity(self):
        result = check("Great question! I'd be happy to help. Some might say it depends.")
        assert not result.passed
        assert len(result.violations) >= 2
        assert result.severity in ("moderate", "severe")

    def test_over_enthusiasm_detected(self):
        result = check("That's amazing!!! 🔥")
        assert not result.passed
        assert any("over_enthusiasm" in v for v in result.violations)

    def test_case_insensitive(self):
        result = check("CERTAINLY! Great Question.")
        assert not result.passed

    def test_normal_conversation_passes(self):
        result = check("Don't know that one — let me grab the audio specialist.")
        assert result.passed


class TestFilterResponse:
    def test_strips_banned_phrase(self):
        result = filter_response("Certainly! Here's the bias circuit info.")
        assert "Certainly!" not in result.cleaned
        assert "bias circuit" in result.cleaned

    def test_cleans_up_artifacts(self):
        result = filter_response("Certainly!   Great question.  Let me check.")
        cleaned = result.cleaned
        assert "  " not in cleaned
        assert cleaned.strip() == cleaned

    def test_empty_after_strip_falls_back_to_original(self):
        # If everything is filtered, don't return empty string
        result = filter_response("Certainly!")
        assert len(result.cleaned) > 0

    def test_passes_clean_text_unchanged(self):
        original = "The bias supply held up. Steady as a rock."
        result = filter_response(original)
        assert result.passed
        assert result.cleaned == original

    def test_logs_drift_on_violation(self):
        from gateway.voice_gate import logger
        with pytest.MonkeyPatch.context() as mp:
            logged = []
            mp.setattr(logger, "warning", lambda msg, *a, **kw: logged.append(msg))
            filter_response("Certainly! I'd be happy to help.")
        assert len(logged) >= 1


class TestDriftNudge:
    def setup_method(self):
        reset_drift_counter()

    def test_no_nudge_when_under_threshold(self):
        record_drift()
        record_drift()
        assert get_drift_nudge() is None

    def test_nudge_after_threshold(self):
        for _ in range(3):
            record_drift()
        nudge = get_drift_nudge()
        assert nudge is not None
        assert "drifted" in nudge.lower()

    def test_reset_clears_counter(self):
        for _ in range(5):
            record_drift()
        reset_drift_counter()
        assert get_drift_nudge() is None


class TestVoiceGateResult:
    def test_default_values(self):
        result = VoiceGateResult(passed=True, original="hi", cleaned="hi")
        assert result.violations == []
        assert result.severity == "none"
