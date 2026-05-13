"""Tests for builder, verifier, eval_runner."""
import pytest
from unittest.mock import patch, AsyncMock


class TestBuilder:
    def test_start_returns_id(self):
        with patch("gateway.builder.asyncio.create_task"):
            from gateway.builder import start
            build_id = start("test build", auto_approve=False)
            assert len(build_id) == 8

    def test_status_not_found(self):
        from gateway.builder import status
        assert status("nonexist") == {"id": "nonexist", "status": "not_found"}

    def test_list_builds(self):
        from gateway.builder import list_builds, init_db
        init_db()
        builds = list_builds(limit=5)
        assert isinstance(builds, list)

    def test_approve_not_running(self):
        from gateway.builder import approve_stage
        assert approve_stage("nonexist", "implement") is False


class TestVerifier:
    @pytest.mark.asyncio
    async def test_verify_runs_tests(self):
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_proc = AsyncMock()
            mock_proc.returncode = 0
            mock_proc.communicate = AsyncMock(return_value=(b"3 passed", b""))
            mock_exec.return_value = mock_proc

            from gateway.verifier import verify
            result = await verify("/tmp/fake")
            assert result["passed"] is True

    @pytest.mark.asyncio
    async def test_verify_timeout(self):
        import asyncio as aio
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            async def slow(*a, **kw):
                await aio.sleep(999)
            mock_proc = AsyncMock()
            mock_proc.communicate = slow
            mock_exec.return_value = mock_proc

            from gateway.verifier import verify
            result = await verify("/tmp/fake", timeout=0.1)
            assert result["passed"] is False


class TestEvalRunner:
    @pytest.mark.asyncio
    async def test_run_smoke(self):
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_proc = AsyncMock()
            mock_proc.returncode = 0
            mock_proc.communicate = AsyncMock(return_value=(b"5 passed", b""))
            mock_exec.return_value = mock_proc

            from gateway.eval_runner import run_smoke
            result = await run_smoke()
            assert "total" in result
            assert "gates" in result
            assert len(result["gates"]) == 5

    def test_compare_improved(self):
        from gateway.eval_runner import compare
        result = compare(
            {"passed": 3, "total": 5},
            {"passed": 5, "total": 5},
        )
        assert result["status"] == "improved"
        assert result["delta"] == 2

    def test_compare_regressed(self):
        from gateway.eval_runner import compare
        result = compare(
            {"passed": 5, "total": 5},
            {"passed": 3, "total": 5},
        )
        assert result["status"] == "regressed"

    def test_compare_unchanged(self):
        from gateway.eval_runner import compare
        result = compare(
            {"passed": 4, "total": 5},
            {"passed": 4, "total": 5},
        )
        assert result["status"] == "unchanged"
