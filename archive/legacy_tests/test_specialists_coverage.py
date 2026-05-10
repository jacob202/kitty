"""
Coverage tests for all specialists.
"""
import sys
import os

import pytest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.core.specialists.registry import SPECIALISTS


class TestSpecialistsCoverage:
    @pytest.mark.parametrize("name,specialist", SPECIALISTS.items())
    def test_specialist_attributes_and_query(self, name, specialist):
        assert hasattr(specialist, "name")
        assert hasattr(specialist, "domain")
        assert specialist.name == name

        with patch("src.core.specialist_framework.query_knowledge_base") as mock_kb, patch(
            "src.space_kitty.llm_client.call_llm"
        ) as mock_llm:
            mock_kb.return_value = [{"text": f"KB content for {name}", "score": 0.9}]
            mock_llm.return_value = f"Mocked response for {name}"

            response = specialist.query(f"What can you tell me about {name}?")

            assert response is not None
            assert hasattr(response, "content")
            assert len(response.content) > 0
            assert response.confidence >= 0
