"""Shared test fixtures for Gateway Builder tests."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest


@pytest.fixture()
def tmp_db(tmp_path: Path) -> Path:
    """Return a path to a temporary SQLite database for Builder tests."""
    db_path = tmp_path / "test_builder_queue.db"
    return db_path


@pytest.fixture()
def tmp_governor_db(tmp_path: Path) -> Path:
    """Return a path to a temporary compute governor database."""
    db_path = tmp_path / "test_compute_governor.db"
    return db_path
