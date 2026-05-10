"""
Tests for response quality critic.
"""
import sys, os, pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.space_kitty.quality_critic import review_draft, extract_learned_rule


class TestReviewDraft:
    def test_directness_flag(self):
        draft = "I might be able to help you perhaps maybe."
        result = review_draft(draft)
        assert result["score"] < 10
        assert any("indirect" in f.lower() for f in result["flags"])

    def test_padding_flag(self):
        draft = "Here is something.\n\n\n\n\n\nDone."
        result = review_draft(draft)
        assert any("padding" in f.lower() for f in result["flags"])

    def test_actionable(self):
        draft = "You should run this command next: do the thing."
        result = review_draft(draft)
        assert result["score"] >= 5

    def test_no_scope_creep(self):
        draft = "Fix this. Also we could add that feature. By the way, another thing."
        result = review_draft(draft)
        assert any("scope" in f.lower() for f in result["flags"])

    def test_include_validation(self):
        draft = "```python\ndef hello(): pass\n```"
        result = review_draft(draft)
        assert any("validation" in f.lower() for f in result["flags"])

    def test_high_score_for_good_draft(self):
        draft = "Run /stuck to see next step. Then do the thing. This is direct."
        result = review_draft(draft)
        assert result["score"] >= 8

    def test_refined_includes_suggestions(self):
        draft = "I think maybe you could perhaps do the thing."
        result = review_draft(draft)
        assert "Critic suggestions:" in result["refined"]


class TestExtractLearnedRule:
    def test_no_correction(self):
        rule = extract_learned_rule("draft", "")
        assert rule == ""

    def test_with_correction(self):
        rule = extract_learned_rule("draft", "Be more direct")
        assert "Rule:" in rule
        assert "Be more direct" in rule

    def test_rule_format(self):
        rule = extract_learned_rule("draft", "Always be brief")
        assert rule.startswith("Rule:")
