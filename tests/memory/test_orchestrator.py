"""Integration tests for MemoryOrchestrator."""

import pytest
from unittest.mock import Mock, patch

from src.memory.orchestrator import MemoryOrchestrator


class TestMemoryOrchestratorIntegration:
    """Integration tests for MemoryOrchestrator."""

    def test_orchestrator_initialization(self):
        """Test that orchestrator initializes correctly."""
        orchestrator = MemoryOrchestrator()
        assert orchestrator is not None
        assert not orchestrator._initialized  # Not initialized until first use

    @patch('src.memory.lightrag_store.LightRAGStore')
    @patch('src.memory.journal_db.JournalDB')
    @patch('src.memory.correction_memory.CorrectionMemory')
    def test_get_context_calls_backends(self, mock_correction, mock_journal, mock_lightrag):
        """Test that get_context calls all backends."""
        # Setup mocks
        mock_lightrag_instance = Mock()
        mock_lightrag_instance.get_relevant_context.return_value = "lightrag result"
        mock_lightrag.return_value = mock_lightrag_instance
        
        mock_journal_instance = Mock()
        mock_journal_instance.get_relevant_context.return_value = "journal result"
        mock_journal.return_value = mock_journal_instance
        
        mock_correction_instance = Mock()
        mock_correction_instance.get_relevant_context.return_value = "correction result"
        mock_correction.return_value = mock_correction_instance
        
        orchestrator = MemoryOrchestrator()
        result = orchestrator.get_context("test query")
        
        # Verify all backends were called
        mock_lightrag_instance.get_relevant_context.assert_called_once_with("test query")
        mock_journal_instance.get_relevant_context.assert_called_once_with("test query")
        mock_correction_instance.get_relevant_context.assert_called_once_with("test query")
        
        # Verify result contains all context
        assert result.success is True
        assert "lightrag result" in result.data
        assert "journal result" in result.data
        assert "correction result" in result.data

    @patch('src.memory.lightrag_store.LightRAGStore')
    @patch('src.memory.journal_db.JournalDB')
    @patch('src.memory.correction_memory.CorrectionMemory')
    def test_store_routes_to_correct_backend(self, mock_correction, mock_journal, mock_lightrag):
        """Test that store routes items to correct backend."""
        orchestrator = MemoryOrchestrator()
        
        # Test knowledge domain
        orchestrator.store({"key": "value"}, domain="knowledge")
        mock_lightrag.assert_called_once()
        mock_lightrag.return_value.add.assert_called_once_with({"key": "value"})
        
        # Reset mocks
        mock_lightrag.reset_mock()
        mock_journal.reset_mock()
        mock_correction.reset_mock()
        
        # Test journal domain
        orchestrator.store({"key": "value"}, domain="journal")
        mock_journal.assert_called_once()
        mock_journal.return_value.add.assert_called_once_with({"key": "value"})
        
        # Reset mocks
        mock_lightrag.reset_mock()
        mock_journal.reset_mock()
        mock_correction.reset_mock()
        
        # Test corrections domain
        orchestrator.store({"key": "value"}, domain="corrections")
        mock_correction.assert_called_once()
        mock_correction.return_value.add.assert_called_once_with({"key": "value"})

    @patch('src.memory.lightrag_store.LightRAGStore')
    @patch('src.memory.journal_db.JournalDB')
    @patch('src.memory.correction_memory.CorrectionMemory')
    def test_retrieve_routes_to_correct_backend(self, mock_correction, mock_journal, mock_lightrag):
        """Test that retrieve routes to correct backend."""
        # Setup mocks
        mock_lightrag_instance = Mock()
        mock_lightrag_instance.search.return_value = [{"id": "1", "content": "test"}]
        mock_lightrag.return_value = mock_lightrag_instance
        
        mock_journal_instance = Mock()
        mock_journal_instance.search.return_value = [{"id": "2", "content": "test"}]
        mock_journal.return_value = mock_journal_instance
        
        mock_correction_instance = Mock()
        mock_correction_instance.search.return_value = [{"id": "3", "content": "test"}]
        mock_correction.return_value = mock_correction_instance
        
        orchestrator = MemoryOrchestrator()
        
        # Test knowledge domain
        result = orchestrator.retrieve("test", domain="knowledge")
        assert result.success is True
        assert len(result.data) == 1
        mock_lightrag_instance.search.assert_called_once_with("test", limit=5)
        
        # Test journal domain
        result = orchestrator.retrieve("test", domain="journal")
        assert result.success is True
        assert len(result.data) == 1
        mock_journal_instance.search.assert_called_once_with("test", limit=5)
        
        # Test corrections domain
        result = orchestrator.retrieve("test", domain="corrections")
        assert result.success is True
        assert len(result.data) == 1
        mock_correction_instance.search.assert_called_once_with("test", limit=5)

    @patch('src.memory.lightrag_store.LightRAGStore')
    @patch('src.memory.journal_db.JournalDB')
    @patch('src.memory.correction_memory.CorrectionMemory')
    def test_delete_routes_to_correct_backend(self, mock_correction, mock_journal, mock_lightrag):
        """Test that delete routes to correct backend."""
        orchestrator = MemoryOrchestrator()
        
        # Test knowledge domain
        orchestrator.delete("test-id", domain="knowledge")
        mock_lightrag.assert_called_once()
        mock_lightrag.return_value.delete.assert_called_once_with("test-id")
        
        # Reset mocks
        mock_lightrag.reset_mock()
        mock_journal.reset_mock()
        mock_correction.reset_mock()
        
        # Test journal domain
        orchestrator.delete("test-id", domain="journal")
        mock_journal.assert_called_once()
        mock_journal.return_value.delete.assert_called_once_with("test-id")
        
        # Reset mocks
        mock_lightrag.reset_mock()
        mock_journal.reset_mock()
        mock_correction.reset_mock()
        
        # Test corrections domain
        orchestrator.delete("test-id", domain="corrections")
        mock_correction.assert_called_once()
        mock_correction.return_value.delete.assert_called_once_with("test-id")

    def test_get_memory_singleton(self):
        """Test that get_memory returns singleton."""
        from src.memory.orchestrator import get_memory
        
        instance1 = get_memory()
        instance2 = get_memory()
        
        assert instance1 is instance2
        assert isinstance(instance1, MemoryOrchestrator)

    @patch('src.memory.lightrag_store.LightRAGStore')
    @patch('src.memory.journal_db.JournalDB')
    @patch('src.memory.correction_memory.CorrectionMemory')
    def test_get_context_handles_backend_errors(self, mock_correction, mock_journal, mock_lightrag):
        """Test that get_context handles backend errors gracefully."""
        # Setup one backend to fail
        mock_lightrag_instance = Mock()
        mock_lightrag_instance.get_relevant_context.side_effect = Exception("LightRAG error")
        mock_lightrag.return_value = mock_lightrag_instance
        
        mock_journal_instance = Mock()
        mock_journal_instance.get_relevant_context.return_value = "journal result"
        mock_journal.return_value = mock_journal_instance
        
        mock_correction_instance = Mock()
        mock_correction_instance.get_relevant_context.return_value = "correction result"
        mock_correction.return_value = mock_correction_instance
        
        orchestrator = MemoryOrchestrator()
        result = orchestrator.get_context("test query")
        
        # Should still succeed with results from working backends
        assert result.success is True
        assert "journal result" in result.data
        assert "correction result" in result.data
        # LightRAG error should not be in successful result
        assert "LightRAG error" not in result.data
