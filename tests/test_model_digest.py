"""Regression tests for gateway.model_digest fail-loud behavior.

The store-read path must surface outages as an explicit "unavailable" note
in the morning brief instead of silently returning an empty list.
"""

from __future__ import annotations

from unittest.mock import patch

from gateway import model_digest
from gateway.model_digest import ModelDigestError


def test_load_recent_events_propagates_error() -> None:
    def boom(limit: int = 10) -> list[dict]:
        raise RuntimeError("db is gone")

    with patch.object(model_digest, "_get_conn", side_effect=boom):
        try:
            model_digest._load_recent_events()
        except ModelDigestError:
            return
        raise AssertionError("expected ModelDigestError to propagate")


def test_section_reports_unavailable_on_store_error(monkeypatch) -> None:
    def boom(limit: int = 10) -> list[dict]:
        raise ModelDigestError("db is gone")

    monkeypatch.setattr(model_digest, "_load_recent_events", boom)
    section = model_digest.get_model_digest_section()
    assert "unavailable" in section


def test_section_empty_when_no_events(monkeypatch) -> None:
    monkeypatch.setattr(model_digest, "_load_recent_events", lambda limit: [])
    assert model_digest.get_model_digest_section() == ""
