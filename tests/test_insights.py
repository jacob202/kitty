"""Tests for gateway.insights — the (deliberately empty) insights substrate.

The route layer was slimmed in Phase 3 to a thin wrapper. These
tests pin the substrate: there is no mock data. ``list_insights``
returns ``[]``; ``dismiss_insight`` is a no-op. The UI gets the
empty state explicitly, not invented cards.
"""

from __future__ import annotations

import pytest

from gateway import insights


class TestListInsights:
    def test_returns_empty_list(self) -> None:
        """The whole point of the new module: no mock data."""
        assert insights.list_insights() == []

    def test_empty_for_any_limit(self) -> None:
        assert insights.list_insights(limit=0) == []
        assert insights.list_insights(limit=10) == []
        assert insights.list_insights(limit=1000) == []

    def test_rejects_negative_limit(self) -> None:
        with pytest.raises(ValueError, match="limit"):
            insights.list_insights(limit=-1)

    def test_rejects_non_int_limit(self) -> None:
        with pytest.raises(ValueError, match="limit"):
            insights.list_insights(limit="ten")  # type: ignore[arg-type]


class TestDismiss:
    def test_returns_false(self) -> None:
        """There is nothing to dismiss — the data is empty."""
        assert insights.dismiss_insight("any-id") is False

    def test_rejects_empty_id(self) -> None:
        with pytest.raises(ValueError, match="insight_id"):
            insights.dismiss_insight("")

    def test_rejects_non_string_id(self) -> None:
        with pytest.raises(ValueError, match="insight_id"):
            insights.dismiss_insight(123)  # type: ignore[arg-type]
