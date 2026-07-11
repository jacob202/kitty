"""Regression tests for gateway.verifier — guard against false-green verdicts.

The key bug: verify() must treat a nonzero pytest exit as a failure even when
the summary line is unparseable (empty run, collection error, crashed worker).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from gateway import verifier


class _FakeProc:
    def __init__(self, returncode: int, out: str, err: str = "") -> None:
        self.returncode = returncode
        self._out = out.encode()
        self._err = err.encode()

    async def communicate(self):
        return self._out, self._err


async def _run(rc: int, out: str) -> dict:
    fake = _FakeProc(rc, out)
    with patch.object(
        verifier.asyncio, "create_subprocess_exec", new=AsyncMock(return_value=fake)
    ):
        return await verifier.verify("/tmp/does-not-matter", timeout=5)


@pytest.mark.asyncio
async def test_nonzero_exit_with_unparseable_output_fails() -> None:
    # Collection error: pytest exits 1 but emits no "passed"/"failed" summary.
    result = await _run(1, "ERROR: collection error\nImportError: no module\n")
    assert result["passed"] is False
    assert result["returncode"] == 1
    assert result["failed_count"] == 0


@pytest.mark.asyncio
async def test_passing_run_reports_passed() -> None:
    result = await _run(0, "3 passed in 0.12s\n")
    assert result["passed"] is True
    assert result["total"] == 3
    assert result["passed_count"] == 3
    assert result["failed_count"] == 0


@pytest.mark.asyncio
async def test_failing_run_reports_failed() -> None:
    result = await _run(1, "2 passed, 1 failed in 0.20s\n")
    assert result["passed"] is False
    assert result["failed_count"] == 1
    assert result["total"] == 3
