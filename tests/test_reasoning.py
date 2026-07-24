"""Tests for gateway/reasoning.py — complexity classifier."""

import pytest

from gateway.reasoning import (
    Classification,
    classify_complexity,
    _REASONING_KEYWORDS,
)


class TestClassification:
    def test_construct_valid(self):
        c = Classification(tier="standard", trigger="default")
        assert c.tier == "standard"
        assert c.trigger == "default"

    def test_rejects_invalid_tier(self):
        with pytest.raises(ValueError, match="tier must be"):
            Classification(tier="unknown", trigger="x")

    def test_rejects_empty_trigger(self):
        with pytest.raises(ValueError, match="trigger must be non-empty"):
            Classification(tier="standard", trigger="")


class TestClassifyComplexity:
    @pytest.mark.parametrize(
        "message,expected_tier,expected_trigger",
        [
            ("hi", "trivial", "short_message"),
            ("thanks", "trivial", "short_message"),
            ("lol ok", "trivial", "short_message"),
            ("ok", "trivial", "short_message"),
            ("hey", "trivial", "short_message"),
            ("good morning", "trivial", "short_message"),
            ("What is the weather?", "standard", "default"),
            ("Tell me a story about dragons", "standard", "default"),
            ("REMIND me to buy milk", "standard", "default"),
            ("what's up today", "trivial", "short_message"),
        ],
    )
    def test_baseline(self, message, expected_tier, expected_trigger):
        c = classify_complexity(message)
        assert c.tier == expected_tier
        assert c.trigger == expected_trigger

    @pytest.mark.parametrize(
        "message",
        [
            "explain how recursion works",
            "why does this error happen?",
            "analyze this codebase",
            "analyse the results",
            "reason about the tradeoffs",
            "think through this design",
            "break down the problem",
            "compare these two approaches",
            "pros and cons of Rust vs Python",
            "step by step instructions",
            "walk me through the setup",
            "how does memory management work",
            "what causes this race condition",
        ],
    )
    def test_reasoning_keyword_triggers_deep(self, message):
        c = classify_complexity(message)
        assert c.tier == "deep"
        assert c.trigger == "reasoning_keyword"

    @pytest.mark.parametrize(
        "message",
        [
            "use your best model for this",
            "use claude for this task",
            "use sonnet please",
            "most capable model needed",
            "smartest model available",
            "best model for the job",
        ],
    )
    def test_best_trigger_triggers_deep(self, message):
        c = classify_complexity(message)
        assert c.tier == "deep"
        assert c.trigger == "best_trigger"

    def test_long_message_triggers_deep(self):
        msg = "I have a very long question " * 30
        assert len(msg) > 500
        c = classify_complexity(msg)
        assert c.tier == "deep"
        assert c.trigger == "length"

    def test_adversarial_short_with_keyword(self):
        c = classify_complexity("why?")
        assert c.tier == "deep"
        assert c.trigger == "reasoning_keyword"

    def test_adversarial_long_no_keyword(self):
        long_msg = "The weather today is sunny and pleasant. " * 30
        assert not any(kw in long_msg.lower() for kw in _REASONING_KEYWORDS)
        c = classify_complexity(long_msg)
        assert c.tier == "deep"
        assert c.trigger == "length"

    def test_adversarial_smalltalk_with_why(self):
        c = classify_complexity("why thank you!")
        assert c.tier == "deep"
        assert c.trigger == "reasoning_keyword"

    def test_health_domain_leans_deep(self):
        c = classify_complexity("tell me about my plan", domain="health")
        assert c.tier == "deep"
        assert c.trigger == "domain"

    def test_normal_domain_is_standard(self):
        c = classify_complexity("tell me about my plan", domain="soul")
        assert c.tier == "standard"
        assert c.trigger == "default"

    def test_case_insensitive_keyword(self):
        c = classify_complexity("EXPLAIN THIS TO ME")
        assert c.tier == "deep"
        assert c.trigger == "reasoning_keyword"

    def test_case_insensitive_best_trigger(self):
        c = classify_complexity("USE YOUR BEST MODEL")
        assert c.tier == "deep"
        assert c.trigger == "best_trigger"

    def test_question_mark_prevents_trivial(self):
        c = classify_complexity("ok?")
        assert c.tier == "standard"

    def test_empty_message_is_trivial(self):
        c = classify_complexity("")
        assert c.tier == "trivial"
        assert c.trigger == "short_message"

    def test_whitespace_only_is_trivial(self):
        c = classify_complexity("   ")
        assert c.tier == "trivial"
        assert c.trigger == "short_message"

    def test_keyword_inside_longer_message(self):
        c = classify_complexity("can you explain something to me please")
        assert c.tier == "deep"
        assert c.trigger == "reasoning_keyword"

    def test_pros_cons_alias(self):
        c = classify_complexity("pros cons of this plan")
        assert c.tier == "deep"
        assert c.trigger == "reasoning_keyword"
