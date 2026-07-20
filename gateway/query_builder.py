"""Typed where-clause builder for safe SQLite parameterisation (audit §2.3).

Problem: many callers in :mod:`gateway.builder_queue` build SQL by
string-concatenating caller-influenced clauses, e.g.
``where_clause = " AND ".join(where_parts)``. Today the strings come
from programmatic, type-checked dicts and parameterised via positional
``?`` bindings, so SQL injection is not possible — but the *string-build
pattern* itself is fragile and easy to break in a future refactor.

Fix: callers pass already-typed :class:`WhereClause` objects (or
:class:`OrderBy` for sorting) into :func:`build_where` and
:func:`build_order_by`. The helpers below turn the typed clauses into a
safe SQL fragment + positional-parameter list. Callers bind the parameters
with ``cursor.execute(sql, params)`` exactly as before — the contract is
unchanged for the DB layer.

Scope: small, explicit, no fluent DSL. Each filter surface in
``builder_queue.py`` migrates in turn. Sibling modules can opt in.

Audit: §2.3 of ``docs/AUDIT_FULL_ENGINEERING_2026-07-20.md``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class WhereClause:
    """A single ``column <op> value`` condition for :func:`build_where`.

    ``column`` is the SQLite column name (caller responsibility — never
    user-controlled). ``op`` selects the comparison; ``value`` is the
    parameter to bind. ``is_null`` short-circuits any op to a NULL check
    (no parameter).
    """

    column: str
    op: str = "="
    value: Any = None
    is_null: bool = False


@dataclass(frozen=True)
class OrderBy:
    """A single ``column DIRECTION`` clause for :func:`build_order_by`."""

    column: str
    direction: str = "ASC"  # one of "ASC" / "DESC"


# Valid SQL operators. Strings only (never user input concatenation via f-string
# elsewhere in the helper).
_OPS_EQ = "="
_OPS_NE = "!="
_VALID_OPS = frozenset({"=", "!=", "<", "<=", ">", ">=", "LIKE", "IN"})
_VALID_DIRECTIONS = frozenset({"ASC", "DESC"})


def build_where(clauses: list[WhereClause]) -> tuple[str, list[Any]]:
    """Turn a list of typed :class:`WhereClause` into a safe WHERE fragment.

    Returns ``(where_sql, params)``. The caller composes::

        where, params = build_where(clauses)
        sql = f"SELECT ... FROM tasks WHERE {where or '1 = 1'} ORDER BY ..."
        cursor.execute(sql, params if where else ())

    Empty input returns ``("", [])``. ``is_null=True`` short-circuits to
    ``column IS NULL`` with no parameter binding. ``op="IN"`` requires a
    ``value`` that is a non-string sequence; the helper unrolls to
    ``column IN (?, ?, ?)`` and binds each element.
    """
    if not clauses:
        return "", []

    parts: list[str] = []
    params: list[Any] = []
    for clause in clauses:
        _validate_column(clause.column)
        if clause.is_null:
            parts.append(f"{clause.column} IS NULL")
            continue
        if clause.op not in _VALID_OPS:
            raise ValueError(
                f"unsupported op {clause.op!r} on column {clause.column!r}; "
                f"valid: {sorted(_VALID_OPS)}"
            )
        if clause.value is None:
            raise ValueError(
                f"WhereClause({clause.column!r}, {clause.op!r}, ...) "
                "has is_null=False but value=None; pass is_null=True"
            )
        if clause.op == "IN":
            if isinstance(clause.value, (str, bytes)):
                raise ValueError(
                    f"WhereClause({clause.column!r}, 'IN', ...) refuses "
                    f"{type(clause.value).__name__}; pass a tuple/list of values."
                )
            for element in clause.value:
                parts.append("?")
                params.append(element)
            placeholders = ", ".join(parts[-len(clause.value) :])
            parts[-len(clause.value) :] = [f"{clause.column} IN ({placeholders})"]
            continue
        parts.append(f"{clause.column} {clause.op} ?")
        params.append(clause.value)
    return " AND ".join(parts), params


def build_order_by(order_by: list[OrderBy]) -> str:
    """Return a safe ``ORDER BY ...`` fragment, or ``""`` if input is empty."""
    if not order_by:
        return ""
    parts: list[str] = []
    for clause in order_by:
        _validate_column(clause.column)
        direction = clause.direction.upper()
        if direction not in _VALID_DIRECTIONS:
            raise ValueError(
                f"unsupported direction {clause.direction!r}; "
                f"valid: {sorted(_VALID_DIRECTIONS)}"
            )
        parts.append(f"{clause.column} {direction}")
    return "ORDER BY " + ", ".join(parts)


def _validate_column(column: str) -> None:
    """Reject columns with whitespace, quotes, parentheses, or other SQL traps.

    The caller chooses columns (these are static, code-side names), but
    rogue edits (a future typo or a refactor that passes a runtime
    string) should fail loudly rather than smuggle SQL into a clause.
    """
    if not isinstance(column, str) or not column:
        raise ValueError("WhereClause.column must be a non-empty string")
    if any(ch in column for ch in " \t\r\n\"'`;()\\"):
        raise ValueError(
            f"column {column!r} contains whitespace, quotes, or other "
            "characters not permitted in a column name; reject and fix the "
            "call site."
        )
    if ".." in column or "." in (column[0], column[-1]) if column else False:
        raise ValueError(
            f"column {column!r} contains a malformed dot sequence "
            "(empty qualifier or consecutive dots)."
        )
    if not column.replace(".", "").replace("_", "").isalnum():
        raise ValueError(
            f"column {column!r} has non-alphanumeric / non-underscore characters."
        )


__all__ = ["WhereClause", "OrderBy", "build_where", "build_order_by"]
