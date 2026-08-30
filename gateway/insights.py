"""User insight cards — deliberately empty substrate for the insights endpoint.

Why this module exists (Phase 3 of the gateway deepening program):
the route used to keep a hard-coded list of mock insight cards
("pattern-morning-weather", "suggestion-daily-loop",
"milestone-100-chats") and serve them as if they were real. That
violates the "Fail loud" prime directive — the UI was being shown
invented data. The new module has no mock data; ``list_insights()``
returns ``[]`` and the route surfaces "no insights" to the UI.

This is one of the two explicit ``try/except ImportError -> in-memory
mock`` shapes from the spec. The other (the 3 hardcoded loops) is
fixed in ``gateway/loops.py``; that one becomes real data because the
data shape is concrete, not invented.
"""

from __future__ import annotations

import logging

logger = logging.getLogger("kitty.insights")


def list_insights(limit: int = 10) -> list[dict]:
    """Return user insight cards. Always empty — there is no real source.

    The empty state is explicit and tested, not silently swallowed.
    When a real insight producer lands (e.g. from ``brief.py`` or
    pattern detection), the body of this function changes; the
    route layer does not.
    """
    if not isinstance(limit, int) or limit < 0:
        raise ValueError(f"limit must be a non-negative int, got {limit!r}")
    return []


def dismiss_insight(insight_id: str) -> bool:
    """No-op dismissal. Returns ``False`` because there is no card to dismiss.

    The wire shape of the endpoint is preserved (the route still
    returns ``{"dismissed": id}``); the underlying state is empty, so
    no card was actually removed.
    """
    if not isinstance(insight_id, str) or not insight_id:
        raise ValueError("insight_id must be a non-empty string")
    return False
