"""Fail-closed admission gate for PAID Mission-review dispatch.

``gateway.builder_loop.run_independent_readonly_review`` is the one place a
paid OpenRouter model gets invoked for Mission plan review. Nothing in the
runtime today reserves or accounts for that spend — the durable
spend-reservation ledger (hold/reserve/settle) that would justify admitting
paid dispatch is separate work, not yet built. Until that exists, the only
honest answer to "is paid Mission-review dispatch admitted right now?" is
NO.

This module is the single source of truth for that answer, and it fails
closed: every call refuses unless the environment variable named by
``ADMISSION_ENV_VAR`` is set to exactly ``ADMISSION_OPT_IN_VALUE``. That
variable is a temporary seam for tests and future integration work only — it
is not a policy decision, and it must never be satisfied by manipulating or
blanking a provider credential. When the real spend-reservation check is
built, it replaces this module's call site in
``gateway/builder_loop.py::run_independent_readonly_review`` (the guard runs
before the provider key is read and before any subprocess is spawned), and
this env-var seam should be deleted at that point.
"""

from __future__ import annotations

import os

ADMISSION_ENV_VAR = "KITTY_PAID_REVIEW_ADMISSION"
ADMISSION_OPT_IN_VALUE = "admitted-no-reservation-yet"

PAID_REVIEW_NOT_ADMITTED_REASON = (
    "paid Mission-review dispatch is awaiting authorization: no durable "
    "spend-reservation exists yet"
)


def is_paid_review_admitted() -> bool:
    """Return True only when the explicit temporary opt-in is set exactly."""
    return os.environ.get(ADMISSION_ENV_VAR, "").strip() == ADMISSION_OPT_IN_VALUE
