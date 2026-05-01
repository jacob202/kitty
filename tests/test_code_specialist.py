"""Tests for KittyCoder (Code Specialist)."""

from src.core.specialists.code import KittyCoderSpecialist


class TestKittyCoderSpecialist:
    def test_instantiation(self):
        coder = KittyCoderSpecialist("Devin", "code", "data/knowledge_bases/code/")
        assert coder.name == "Devin"
        assert coder.domain == "code"
        assert len(coder.personality) > 0

    def test_system_prompt_has_dev_personality(self):
        coder = KittyCoderSpecialist("Devin", "code", "data/knowledge_bases/code/")
        prompt = coder._get_system_prompt()
        assert "Devin" in prompt

    def test_safety_topics_has_code_risks(self):
        coder = KittyCoderSpecialist("Devin", "code", "data/knowledge_bases/code/")
        topics = coder._get_safety_topics()
        assert "rm -rf" in topics or "eval(" in topics

    def test_domain_matches(self):
        coder = KittyCoderSpecialist("Devin", "code", "data/knowledge_bases/code/")
        assert coder.domain == "code"

    def test_query_method_exists(self):
        coder = KittyCoderSpecialist("Devin", "code", "data/knowledge_bases/code/")
        assert hasattr(coder, "query")
