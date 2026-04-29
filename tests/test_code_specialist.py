"""
Tests for Alex (Code Specialist).
"""
import sys, os, pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.core.specialists.code import KittyCoderSpecialist


class TestKittyCoderSpecialist:
    def test_answer_python(self):
        alex = KittyCoderSpecialist()
        result = alex.answer("How to loop in Python?")
        assert "list comprehension" in result["answer"]
        assert result["source"] != "no source found"
        assert result["confidence"] > 0.5

    def test_answer_javascript(self):
        alex = KittyCoderSpecialist()
        result = alex.answer("iterate array javascript")
        assert "map()" in result["answer"] or "forEach" in result["answer"]
        assert result["source"] != "no source found"

    def test_answer_unknown(self):
        alex = KittyCoderSpecialist()
        result = alex.answer("unknown query about cooking")
        assert result["confidence"] < 0.5
        assert result["source"] == "no source found"

    def test_explain(self):
        alex = KittyCoderSpecialist()
        result = alex.explain("for i in range(10): print(i)")
        assert "code:" in result["explanation"]
        assert result["source"] == "Direct code analysis"
