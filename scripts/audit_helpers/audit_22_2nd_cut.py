#!/usr/bin/env python3
"""Audit §2.2 second cut — extract lease lifecycle from gateway.builder_queue.

Marker-based extraction via the AST. We:
1. Find the 10 functions that have been moved to gateway.builder_queue_leases.
2. Delete them in reverse line order so earlier line indices don't shift.
3. Inject a single facade import for the new leases module immediately
   after the existing ``from .builder_queue_db import (...)`` block at
   the top of the file.
4. Assert the post-write file no longer defines any of the extracted
   functions.

Run after the audit §2.2 second-cut new module
(``gateway/builder_queue_leases.py``) has been written. This script only
modifies the parent (``builder_queue.py``).
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

QUEUE_PY = Path("$(dirname $(realpath "$0"))/../../gateway/builder_queue.py")
src = QUEUE_PY.read_text(encoding="utf-8")
original_lines = src.count("\n") + 1
original_len = len(src)

# Functions to move to gateway.builder_queue_leases.
EXTRACT_NAMES = {
    "_generate_lease_token",
    "_claim_impl",
    "claim_task",
    "claim_next",
    "_transition_subject",
    "worker_transition_task",
    "worker_release_task",
    "operator_release_task",
    "recover_expired_leases",
    "renew_lease",
}

tree = ast.parse(src)
extracted_positions: list[tuple[int, int, str]] = []
for node in tree.body:
    name = getattr(node, "name", None)
    if name in EXTRACT_NAMES:
        # ast line numbers are 1-indexed inclusive; convert to 0-indexed half-open
        # spans so deletions are unambiguous.
        extracted_positions.append((node.lineno - 1, node.end_lineno, name))

found_names = {p[2] for p in extracted_positions}
missing = EXTRACT_NAMES - found_names
if missing:
    print(f"FAIL: missing extractable functions: {sorted(missing)}", file=sys.stderr)
    sys.exit(1)

# Reverse-order deletion so earlier line indices stay valid.
extracted_positions.sort(reverse=True)
lines = src.splitlines(keepends=True)
for start, end, name in extracted_positions:
    span_text = "".join(lines[start:end])
    first = span_text.splitlines()[0].strip()[:60] if span_text.splitlines() else "(empty)"
    del lines[start:end]
    print(f"  removed L{start + 1}-L{end} ({end - start} lines): {name} — {first}")

src_after = "".join(lines)

# Inject the facade import immediately after the existing multi-line
# ``from .builder_queue_db import (...)`` block.
fa_marker = "from .builder_queue_db import (  # noqa: E402"
fa_start = src_after.find(fa_marker)
assert fa_start >= 0, (
    "could not locate existing `.builder_queue_db` facade import"
)
fa_close = src_after.find("\n)", fa_start)
assert fa_close > fa_start, (
    "could not find closing paren of `.builder_queue_db` import block"
)

NEW_FACADE = """

# ---------------------------------------------------------------------------
# Re-exports from gateway.builder_queue_leases (audit §2.2 second cut).
# Keep ``from gateway.builder_queue import X`` working for
# ``gateway.builder_runner`` (renew_lease heartbeat), ``builder_attempt``
# (claim / release worker paths), the CLI, and tests.
# ---------------------------------------------------------------------------
from .builder_queue_leases import (
    claim_task,
    claim_next,
    worker_transition_task,
    worker_release_task,
    operator_release_task,
    recover_expired_leases,
    renew_lease,
)
"""

insert_pos = fa_close + len("\n)")
src_final = src_after[:insert_pos] + NEW_FACADE + src_after[insert_pos:]

QUEUE_PY.write_text(src_final, encoding="utf-8")
new_len = len(src_final)
new_lines = src_final.count("\n") + 1

print(f"\nWrote {QUEUE_PY}")
print(f"  Original: {original_lines} lines ({original_len} chars)")
print(f"     New : {new_lines} lines ({new_len} chars)")
print(f"   Delta : {new_lines - original_lines:+d} lines ({new_len - original_len:+d} chars)")

# Post-write assertions
assert (
    src_final.count(
        "from .builder_queue_leases import (\n    claim_task,\n    claim_next,"
    )
    == 1
), "expected exactly one facade import for the leases module"

for name in EXTRACT_NAMES:
    n = src_final.count(f"\ndef {name}(")
    assert n == 0, (
        f"function {name!r} still defined in builder_queue.py after extraction "
        f"({n} occurrences found)"
    )

print("\n§2.2 second cut (leases extraction) applied successfully — all assertions passed.")
