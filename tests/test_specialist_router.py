"""
Tests for specialist router.
"""
import sys, os, pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.core.specialists.router import route_specialist, get_specialist_context


class TestSpecialistRouter:
    def test_route_code(self):
        result = route_specialist("Fix this Python function")
        assert result == "KittyCoder"

    def test_route_fix_car(self):
        result = route_specialist("Fix my car engine")
        assert result == "mike"

    def test_route_research(self):
        result = route_specialist("Search for papers")
        assert result == "research"

    def test_route_no_match(self):
        result = route_specialist("hello world")
        assert result is None

    def test_get_context_found(self):
        ctx = get_specialist_context("alex")
        assert "name" in ctx
        assert ctx["name"] == "alex"

    def test_get_context_not_found(self):
        ctx = get_specialist_context("nonexistent")
        assert ctx["source"] == "not found"
