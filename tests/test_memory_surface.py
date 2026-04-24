"""Tests for src/core/memory_surface.py"""
import pytest
from src.core import memory_surface


def test_empty_store_returns_empty_string(monkeypatch):
    monkeypatch.setattr(memory_surface, "_load_entities", lambda: [])
    assert memory_surface.surface_memory("sansui repair") == ""


def test_matching_entity_appears_in_output(monkeypatch):
    entities = [
        {
            "name": "Sansui AU-7900",
            "entityType": "equipment",
            "observations": ["AU-7900 amplifier", "needs recap"],
        }
    ]
    monkeypatch.setattr(memory_surface, "_load_entities", lambda: entities)
    result = memory_surface.surface_memory("sansui repair")
    assert "Sansui AU-7900" in result
    assert "[Memory]" in result


def test_non_matching_entity_excluded(monkeypatch):
    entities = [
        {
            "name": "Python",
            "entityType": "language",
            "observations": ["general purpose programming language"],
        }
    ]
    monkeypatch.setattr(memory_surface, "_load_entities", lambda: entities)
    assert memory_surface.surface_memory("sansui repair") == ""


def test_top_k_limits_results(monkeypatch):
    entities = [
        {"name": f"entity{i}", "entityType": "test", "observations": ["sansui thing"]}
        for i in range(10)
    ]
    monkeypatch.setattr(memory_surface, "_load_entities", lambda: entities)
    result = memory_surface.surface_memory("sansui", top_k=3)
    assert result.count("- entity") == 3


def test_empty_query_returns_empty_string(monkeypatch):
    monkeypatch.setattr(memory_surface, "_load_entities", lambda: [{"name": "x", "entityType": "t", "observations": ["y"]}])
    assert memory_surface.surface_memory("") == ""
    assert memory_surface.surface_memory("   ") == ""
