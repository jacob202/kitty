"""
Tests for specialist answer validator.
"""
import sys, os, pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.core.specialists.validator import validate_answer


class TestSpecialistValidator:
    def test_valid_answer(self):
        result = validate_answer("kelly", "Exercise 3 sets, 30 min cardio.", "config/specialists/kelly.md")
        assert result["valid"] is True
        assert result["confidence"] >= 0.5

    def test_missing_source(self):
        result = validate_answer("kelly", "Do the workout.", "")
        assert result["valid"] is False
        assert any("source" in i.lower() for i in result["issues"])

    def test_short_answer(self):
        result = validate_answer("alex", "Hi.", "config/specialists/alex.md")
        assert result["confidence"] < 0.8
        assert any("short" in i.lower() for i in result["issues"])

    def test_no_clear_ending(self):
        result = validate_answer("mike", "Check the engine.", "config/specialists/mike.md")
        assert result["confidence"] < 0.8 or any("ending" in i.lower() for i in result["issues"])

    def test_with_source(self):
        result = validate_answer("alex", "Use list comprehension. Source: Python docs.", "config/specialists/alex.md")
        assert result["valid"] is True
        assert result["source"] != "no source provided"
