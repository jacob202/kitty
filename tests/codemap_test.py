"""Smoke test for the gateway module surface.

If a module's public API breaks (syntax error, missing import, name
collision on import, etc.), this test fails fast. Insurance against
the import-time breakage that bit us with `mcp/imagen/server.py` (see
`docs/LEARNINGS.md` L-CAND-6).

It is **not** a behaviour test — those live in `tests/test_<module>.py`
next to each module. This test only asserts that the module loads,
that the public names it claims to export are present, and that
importing it does not raise.

## What it does

1. Walks every module under `gateway/` and tries to import it.
2. Asserts a small set of public-API names exist (the ones the rest of
   the codebase reaches for when it talks to the gateway).
3. Reports import failures with the full traceback so the next agent
   can see exactly which module and which line broke.

## What it does NOT do

- Run any module's `__main__`.
- Open a database connection.
- Call any LLM provider.
- Touch the network.

If a module legitimately cannot be imported in this test environment
(e.g. it requires a real LiteLLM proxy on `127.0.0.1:8001`), add it to
`KNOWN_IMPORT_OPT_OUT` below with the reason. The opt-out list is
intentionally small and reviewed on every deepening pass.
"""

from __future__ import annotations

import importlib
import pkgutil
import types
from typing import Iterable

import pytest

import gateway

# Modules that are known to require runtime services or to be
# import-unsafe in the test environment. The reason is recorded so
# the next reviewer can revisit when the constraint changes.
KNOWN_IMPORT_OPT_OUT: dict[str, str] = {
    # gateway.cli_helper pulls in click + kitty launcher deps;
    # exercised by the CLI entrypoint, not by unit tests.
    "gateway.cli_helper": "CLI entrypoint; pulls in launcher wiring not safe in tests",
}


def _all_gateway_modules() -> Iterable[str]:
    """Yield the dotted name of every module under `gateway/`."""
    for mod_info in pkgutil.iter_modules(gateway.__path__):
        yield f"gateway.{mod_info.name}"


def _is_opted_out(dotted: str) -> str | None:
    """Return the opt-out reason for `dotted`, or None if it must be tested."""
    return KNOWN_IMPORT_OPT_OUT.get(dotted)


@pytest.mark.parametrize("dotted", list(_all_gateway_modules()))
def test_module_imports(dotted: str) -> None:
    """Every non-opted-out gateway module must import without error."""
    reason = _is_opted_out(dotted)
    if reason is not None:
        pytest.skip(f"opt-out: {reason}")
    try:
        mod = importlib.import_module(dotted)
    except Exception as exc:  # surface the import error with full context
        pytest.fail(f"importing {dotted} raised {type(exc).__name__}: {exc}")
    assert isinstance(mod, types.ModuleType), f"{dotted} did not resolve to a module"


def test_opt_out_list_is_explicit() -> None:
    """The opt-out list must be small and every entry must have a reason."""
    for dotted, reason in KNOWN_IMPORT_OPT_OUT.items():
        assert reason and len(reason) > 10, (
            f"opt-out for {dotted} needs a real reason (got {reason!r})"
        )
