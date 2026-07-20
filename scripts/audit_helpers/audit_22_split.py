#!/usr/bin/env python3
"""Audit §2.2 first cut — split gateway.builder_queue.py into a façade.

Marker-based extraction. Each region is anchored on stable markers that
already exist in the file, so this script is robust against minor
whitespace drift (3-vs-4-space docstring indents, trailing-newline
variations) that broke the verbatim oldString approach.

Reads :file:`gateway/builder_queue.py`, replaces three ranges with explicit
``from .builder_queue_db import (...)`` blocks, writes the result back.
The new module :file:`gateway/builder_queue_db.py` (created separately)
owns the DB layer.
"""
from __future__ import annotations

import sys
from pathlib import Path

QUEUE_PY = Path("$(dirname $(realpath "$0"))/../../gateway/builder_queue.py")
src = QUEUE_PY.read_text(encoding="utf-8")
original_len = len(src)
original_lines = src.count("\n")

# ---------------------------------------------------------------------------
# Region 1: state constants + error classes -> facade re-import
# ---------------------------------------------------------------------------

# Anchor: the "State constants" section banner.
r1_start_marker = "# State constants (Section 4.3"
r1_start = src.find(r1_start_marker)
assert r1_start >= 0, "R1: 'State constants' section banner not found"

# Tail-anchor: the closing docstring of the last error class
# (DataCorruptionError). Walk forward past its docstring close + newline.
last_class_marker = "class DataCorruptionError(RuntimeError):"
last_class_at = src.find(last_class_marker, r1_start)
assert last_class_at >= 0, "R1: DataCorruptionError class def not found"

# The docstring opens on the next text line after the colon. Search for
# the FIRST triple-quote after the class def, then the next triple-quote
# past it (the close), and consume the resulting close + TLN.
first_quote_after_class = src.find('"""', last_class_at + len(last_class_marker))
second_quote_after_class = src.find('"""', first_quote_after_class + 3)
assert first_quote_after_class >= 0 and second_quote_after_class >= 0, (
    "R1: could not find both docstring quotes for DataCorruptionError"
)
r1_end = second_quote_after_class + len('"""')
# Include the trailing newline if present so post-replacement the
# discovered region matches what was visibly in the file.
if r1_end < len(src) and src[r1_end] == "\n":
    r1_end += 1

old1 = src[r1_start:r1_end]
new1 = '''# ---------------------------------------------------------------------------
# State constants + error classes (Section 4.3) — extracted to
# gateway.builder_queue_db (audit §2.2). Re-exported below so ``from
# gateway.builder_queue import X`` and ``import gateway.builder_queue as bq``
# keep working for tests and sibling modules
# (gateway.builder_attempt, gateway.builder_runner, gateway.builder_initiative,
# gateway.builder_cli, tests/...).
# ---------------------------------------------------------------------------
from .builder_queue_db import (
    # Task state names + transition map
    QUEUED, CLAIMED, RUNNING, PR_OPENED, AWAITING_REVIEW,
    DONE, FAILED, CANCELLED, BLOCKED,
    TERMINAL_STATES, _VALID_STATES, LEGAL_TRANSITIONS,
    # Error classes
    TaskNotFoundError, IllegalTransitionError,
    LeaseConflictError, BranchLeaseConflictError, DataCorruptionError,
)
'''

assert old1 in src, "R1: extracted region not found in src"
src = src.replace(old1, new1, 1)
print(f"R1 OK: extracted {len(old1)} chars, replaced with {len(new1)} chars")

# ---------------------------------------------------------------------------
# Region 2: schema section + _SCHEMA_SQL -> brief comment
# ---------------------------------------------------------------------------

r2_start_marker = "# Schema (Phase 1A"
r2_start = src.find(r2_start_marker)
assert r2_start >= 0, "R2: 'Schema' section banner not found"

# Tail-anchor: the last line of _SCHEMA_SQL ends with `;` followed by the
# closing `"""` and a newline, then a blank line, then "# Run lifecycle
# states..." (which we keep).
last_sql_stmt = "ON branch_leases(worker_id);"
last_sql_idx = src.find(last_sql_stmt, r2_start)
assert last_sql_idx >= 0, "R2: last SQL statement not found"
schema_close = src.find('"""', last_sql_idx + len(last_sql_stmt))
assert schema_close >= 0, "R2: schema closing triple-quote not found"
r2_end = schema_close + len('"""')
if r2_end < len(src) and src[r2_end] == "\n":
    r2_end += 1

old2 = src[r2_start:r2_end]
new2 = '''# ---------------------------------------------------------------------------
# SQLite schema (Phase 1A — tasks + events; runs/pr_links/artifacts future).
# The DDL has moved to gateway.builder_queue_db._SCHEMA_SQL (audit §2.2).
# This banner stays so the surrounding run-state section remains visually
# grouped with the schema location.
# ---------------------------------------------------------------------------
'''

assert old2 in src, "R2: extracted region not found in src"
src = src.replace(old2, new2, 1)
print(f"R2 OK: extracted {len(old2)} chars, replaced with {len(new2)} chars")

# ---------------------------------------------------------------------------
# Region 3: connection / init helpers (_PRAGMAS .. connect) -> import block
# ---------------------------------------------------------------------------

r3_start_marker = "_PRAGMAS = ("
r3_start = src.find(r3_start_marker)
assert r3_start >= 0, "R3: '_PRAGMAS = (' not found"

# Tail-anchor: connect()'s last line is `return conn`. Take the LAST
# occurrence after r3_start; that's connect's close.
last_return_marker = "return conn\n"
connect_close_idx = src.rfind(last_return_marker, r3_start)
assert connect_close_idx > r3_start, "R3: 'return conn' tail not found"
r3_end = connect_close_idx + len(last_return_marker)

old3 = src[r3_start:r3_end]
new3 = '''# ---------------------------------------------------------------------------
# Connection / init helpers — extracted to gateway.builder_queue_db
# (audit §2.2). Re-imported below so callers (`bq.init_db(...)`,
# `bq.connect(...)`) and the test suite still work unchanged.
# ---------------------------------------------------------------------------
from .builder_queue_db import init_db, connect
'''

assert old3 in src, "R3: extracted region not found in src"
src = src.replace(old3, new3, 1)
print(f"R3 OK: extracted {len(old3)} chars, replaced with {len(new3)} chars")

# ---------------------------------------------------------------------------
# Sanity checks before writing
# ---------------------------------------------------------------------------

# Each facade import block added exactly once.
assert src.count("from .builder_queue_db import (\n    # Task state names") == 1, (
    "expected exactly one task-state-mask import block"
)
assert src.count("from .builder_queue_db import init_db, connect") == 1, (
    "expected exactly one init_db/connect re-import block"
)

# Regression guard: moved symbols must NOT be duplicated.
for symbol in (
    "QUEUED = ",
    "class TaskNotFoundError",
    "_SCHEMA_SQL = ",
    "_PRAGMAS = (",
    "def init_db",
    "def connect",
):
    n = src.count(symbol)
    assert n <= 1, (
        f"Symbol {symbol!r} appears {n} times after edit "
        f"(must be 0 in facade — moved to builder_queue_db.py)"
    )

QUEUE_PY.write_text(src, encoding="utf-8")
new_len = len(src)
new_lines = src.count("\n")
print(f"\nWrote {QUEUE_PY}")
print(f"Original: {original_lines} lines ({original_len} chars)")
print(f"     New: {new_lines} lines ({new_len} chars)")
print(f"   Delta: {new_lines - original_lines:+d} lines  "
      f"({new_len - original_len:+d} chars)")
print("All three replacements applied successfully.")
