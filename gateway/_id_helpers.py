"""Shared ID-generation helpers.

Lifted out of ``gateway.builder_queue`` and ``gateway.builder_queue_runs``
during the \u00a72.2 third-cut cleanup to remove the duplicated ``_to_base36``
helper. Public utility: callers pick the bits they need.

No cycle dependency on any other gateway module (does not import
``gateway.builder_queue`` or any sibling). Safe to import from any
gateway submodule.
"""

from __future__ import annotations

import secrets
import time

_BASE36_DIGITS = "0123456789abcdefghijklmnopqrstuvwxyz"


def to_base36(n: int) -> str:
    """Encode a non-negative integer as lowercase base36 (no leading zeros)."""
    if n < 0:
        raise ValueError("base36 encoding requires a non-negative integer")
    if n == 0:
        return "0"
    out: list[str] = []
    while n > 0:
        n, rem = divmod(n, 36)
        out.append(_BASE36_DIGITS[rem])
    return "".join(reversed(out))


def generate_id_with_base36(prefix: str) -> str:
    """Return ``<prefix>_<base36_unix_ms>_<hex4>`` (time-sortable ID).

    ``base36`` of the millisecond timestamp keeps the ID compact and
    monotonically increasing on a single machine; ``hex4`` adds 16 bits of
    local disambiguation so two creates in the same millisecond do not
    collide in practice.
    """
    unix_ms = int(time.time() * 1000)
    return f"{prefix}_{to_base36(unix_ms)}_{secrets.token_hex(2)}"


# Layering note
# --------------
# ``generate_id_with_base36(prefix)`` is the canonical entry point for any
# new code that needs a time-sortable identifier. The lower-level
# ``to_base36`` is exposed only because tests/test_builder_queue_runs.py
# (``IdHelpersTest``) exercises it directly with algorithmic edge cases
# (e.g. ``to_base36(-1)`` raises, ``to_base36(0)`` is "0"). New duplication
# of the unix_ms->base36->hex4 triple is exactly the bug this helper was
# extracted to prevent.


__all__ = ["to_base36", "generate_id_with_base36"]
