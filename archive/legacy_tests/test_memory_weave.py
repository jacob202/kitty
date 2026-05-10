"""Regression tests for MemoryWeave database path wiring."""

import importlib


def test_memory_weave_imports_with_configured_db_path():
    module = importlib.import_module("src.memory.memory_weave")

    assert module._DB_PATH.name == "memory_weave.db"
