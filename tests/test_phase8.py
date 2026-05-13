"""Tests for Phase 8-10: sync, deploy, search."""
import pytest
from unittest.mock import patch


class TestSync:
    def test_export_returns_dict(self):
        from gateway.sync import export_snapshot
        snapshot = export_snapshot()
        assert isinstance(snapshot, dict)
        assert "version" in snapshot
        assert "memories" in snapshot
        assert "journal_entries" in snapshot

    def test_import_empty(self):
        from gateway.sync import import_snapshot
        assert import_snapshot({}) == 0
        assert import_snapshot("not dict") == 0


class TestDeploy:
    @pytest.mark.asyncio
    async def test_unsupported_platform(self):
        from gateway.deploy import deploy
        result = await deploy("/tmp", platform="heroku")
        assert "error" in result


class TestSearch:
    def test_search_returns_structure(self):
        from gateway.search import search
        result = search("test query")
        assert "memories" in result
        assert "knowledge" in result
        assert "journal" in result
        assert "todos" in result
        assert result["query"] == "test query"
