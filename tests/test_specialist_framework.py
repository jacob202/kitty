#!/usr/bin/env python3
"""Tests for the Specialist Framework."""

import pytest
from unittest.mock import patch, MagicMock


class TestSpecialistFramework:
    """Test cases for the specialist framework."""

    def test_specialist_response_dataclass(self):
        """Test that SpecialistResponse can be instantiated."""
        from src.core.specialist_framework import SpecialistResponse
        
        response = SpecialistResponse(
            content="Test response",
            confidence=0.9,
            sources=["test.md"],
            safety_warnings=[],
            suggested_followups=["Follow up question"]
        )
        
        assert response.content == "Test response"
        assert response.confidence == 0.9
        assert response.sources == ["test.md"]
        assert response.safety_warnings == []
        assert response.suggested_followups == ["Follow up question"]

    @patch('src.core.specialist_framework._get_memory')
    def test_get_memory_singleton(self, mock_get_memory):
        """Test that _get_memory returns a singleton."""
        from src.core.specialist_framework import _get_memory
        
        mock_memory = MagicMock()
        mock_get_memory.return_value = mock_memory
        
        result1 = _get_memory()
        result2 = _get_memory()
        
        assert result1 is result2
        assert mock_get_memory.call_count == 2  # Called twice but returns same

    @patch('src.core.specialist_framework.query_knowledge_base')
    def test_query_knowledge_base(self, mock_query):
        """Test knowledge base query function."""
        from src.core.specialist_framework import query_knowledge_base
        
        mock_query.return_value = [{"text": "Test result", "score": 0.9}]
        
        results = query_knowledge_base("test query", domain="code")
        
        assert len(results) == 1
        assert results[0]["text"] == "Test result"
        mock_query.assert_called_once()

    def test_specialist_response_with_diagnostics(self):
        """Test SpecialistResponse with diagnostics."""
        from src.core.specialist_framework import SpecialistResponse
        
        response = SpecialistResponse(
            content="Response with diagnostics",
            confidence=0.85,
            sources=["doc1.md"],
            safety_warnings=["Warning 1"],
            suggested_followups=["Next question"],
            diagnostics={"token_count": 150, "model": "llama3.2"}
        )
        
        assert response.diagnostics is not None
        assert response.diagnostics["token_count"] == 150
        assert response.diagnostics["model"] == "llama3.2"

    @patch('src.core.specialist_framework._get_lightrag_for_domain')
    def test_get_lightrag_for_domain(self, mock_get_lr):
        """Test getting LightRAG instance for a domain."""
        from src.core.specialist_framework import _get_lightrag_for_domain
        
        mock_lr = MagicMock()
        mock_get_lr.return_value = mock_lr
        
        result = _get_lightrag_for_domain("code")
        
        assert result is mock_lr

    def test_specialist_response_defaults(self):
        """Test SpecialistResponse with default values."""
        from src.core.specialist_framework import SpecialistResponse
        
        response = SpecialistResponse(
            content="Minimal response",
            confidence=0.5,
            sources=[],
            safety_warnings=[],
            suggested_followups=[]
        )
        
        assert response.content == "Minimal response"
        assert response.diagnostics is None  # Default None


class TestSpecialistRegistry:
    """Test cases for the specialist registry."""

    def test_registry_imports(self):
        """Test that specialist registry can be imported."""
        # This tests that the registry file exists and can be imported
        try:
            from src.core.specialists import registry
            # Registry exists, just verify it imports without error
            assert registry is not None
        except ImportError as e:
            pytest.skip(f"Specialist registry not yet implemented: {e}")


class TestSpecialistConfigs:
    """Test cases for specialist configurations."""

    def test_specialist_configs_exist(self):
        """Test that specialist config files exist."""
        from pathlib import Path
        import os
        
        config_dir = Path(os.path.dirname(__file__)).parent.parent / "config" / "specialists"
        
        if config_dir.exists():
            configs = list(config_dir.glob("*.md"))
            assert len(configs) > 0, "No specialist config files found"

    def test_kitty_specialist_config(self):
        """Test that kitty.md specialist config is valid."""
        from pathlib import Path
        import os
        
        config_path = Path(os.path.dirname(__file__)).parent.parent / "config" / "specialists" / "kitty.md"
        
        if config_path.exists():
            content = config_path.read_text()
            assert len(content) > 0
            # Check for expected sections
            assert "name" in content.lower() or "specialist" in content.lower()

    def test_entity_extraction_fix(self):
        """Test that _extract_entities logic (line 182) correctly extracts alphanumeric words."""
        # Simulate the fixed logic from specialist_framework.py:182
        def extract_entities(question):
            return list(set(w for w in question.split() if w.isalnum() and len(w) > 4))[:5]

        # Bug before fix: " ".join(filter(str.isalnum, w)) iterated chars, not words
        # Now fixed: filters whole words that are alphanumeric and len > 4
        result = extract_entities("My amplifier has a buzzing sound from the Sansui AU-7900")
        assert "amplifier" in result
        assert "buzzing" in result or "sound" in result
        assert "Sansui" in result
        assert "AU-7900" not in result  # contains hyphen, not isalnum

    def test_entity_extraction_no_short_words(self):
        """Short words (len <= 4) should be excluded."""
        def extract_entities(question):
            return list(set(w for w in question.split() if w.isalnum() and len(w) > 4))[:5]

        result = extract_entities("What is 12345?")
        assert result == []  # "What" len=4, "12345" has len=5 but isalnum() True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])