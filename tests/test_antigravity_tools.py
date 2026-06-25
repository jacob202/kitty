"""Tests for antigravity/Orca-style tools."""

import pytest

from gateway.antigravity_tools import get_tools, invoke_tool
from gateway.async_feedback import async_feedback
from gateway.task_boundary import task_boundary


class TestAntigravityTools:
    """Test antigravity tool integration."""

    def test_get_tools_returns_list(self):
        """Tools should be available."""
        tools = get_tools()
        assert isinstance(tools, list)
        assert len(tools) > 0

    def test_task_boundary_tool_available(self):
        """task_boundary tool should be in the list."""
        tools = get_tools()
        tool_names = {t["name"] for t in tools}
        assert "task_boundary" in tool_names

    def test_notify_user_tool_available(self):
        """notify_user tool should be in the list."""
        tools = get_tools()
        tool_names = {t["name"] for t in tools}
        assert "notify_user" in tool_names

    @pytest.mark.asyncio
    async def test_task_boundary_open(self):
        """Should open a task boundary."""
        result = await invoke_tool("task_boundary", {
            "action": "open",
            "name": "Test Task",
            "summary": "Testing task boundaries"
        })
        assert result["success"]
        assert "task_id" in result

    @pytest.mark.asyncio
    async def test_task_boundary_update(self, tmp_path):
        """Should update task progress."""
        # Open a task
        open_result = await invoke_tool("task_boundary", {
            "action": "open",
            "name": "Update Test",
            "summary": "Testing updates"
        })
        task_id = open_result["task_id"]

        # Update it
        result = await invoke_tool("task_boundary", {
            "action": "update",
            "task_id": task_id,
            "status": "in_progress",
            "summary": "Working on it"
        })
        assert result["success"]

    @pytest.mark.asyncio
    async def test_task_boundary_close(self, tmp_path):
        """Should close a task."""
        # Open a task
        open_result = await invoke_tool("task_boundary", {
            "action": "open",
            "name": "Close Test",
            "summary": "Testing close"
        })
        task_id = open_result["task_id"]

        # Close it
        result = await invoke_tool("task_boundary", {
            "action": "close",
            "task_id": task_id,
            "summary": "Done",
            "success": True
        })
        assert result["success"]

    @pytest.mark.asyncio
    async def test_notify_user(self):
        """Should send notification."""
        result = await invoke_tool("notify_user", {
            "message": "Test notification",
            "priority": "info"
        })
        assert result["success"]

    @pytest.mark.asyncio
    async def test_check_feedback_no_file(self):
        """Should return empty when no feedback exists."""
        result = await invoke_tool("check_feedback", {
            "artifact_path": "/nonexistent/path.md"
        })
        assert result["success"]
        assert result["feedback_count"] == 0


class TestCodebaseSearch:
    """Test codebase search functionality."""

    @pytest.mark.asyncio
    async def test_codebase_search_available(self):
        """codebase_search tool should be available."""
        tools = get_tools()
        tool_names = {t["name"] for t in tools}
        assert "codebase_search" in tool_names

    @pytest.mark.asyncio
    async def test_codebase_search_requires_query_without_loading_search(self, monkeypatch):
        """Should require query parameter before loading heavyweight search dependencies."""
        def fail_if_loaded():
            raise AssertionError("codebase search should not load without a query")

        monkeypatch.setattr("gateway.antigravity_tools.get_codebase_search", fail_if_loaded)
        result = await invoke_tool("codebase_search", {})
        assert not result["success"]
        assert "error" in result


class TestWebTools:
    """Test web tracking tools."""

    @pytest.mark.asyncio
    async def test_web_capture_requires_params(self):
        """Should require url and content."""
        result = await invoke_tool("web_capture", {})
        assert not result["success"]

    @pytest.mark.asyncio
    async def test_web_compare_requires_url(self):
        """Should require url parameter."""
        result = await invoke_tool("web_compare", {})
        assert not result["success"]

    @pytest.mark.asyncio
    async def test_web_compare_handles_missing_dependencies(self, monkeypatch):
        """Should return a clear unavailable message when tracker deps are missing."""
        import gateway.web_tracker as web_tracker_module

        monkeypatch.setattr(web_tracker_module, "TRACKER_AVAILABLE", False)
        result = await invoke_tool("web_compare", {"url": "https://example.com"})
        assert result["success"]
        assert "not available" in result["comparison"]


class TestTeamProtocol:
    """Test team coordination tools."""

    @pytest.mark.asyncio
    async def test_share_discovery(self):
        """Should share a discovery."""
        result = await invoke_tool("share_discovery", {
            "discovery": "Test discovery",
            "tags": ["test"],
            "agent_name": "test-agent"
        })
        assert result["success"]

    @pytest.mark.asyncio
    async def test_get_discoveries(self):
        """Should retrieve discoveries."""
        result = await invoke_tool("get_discoveries", {})
        assert result["success"]
        assert "discoveries" in result


class TestTaskBoundaryModule:
    """Test task_boundary module directly."""

    def test_task_boundary_summary(self):
        """Should generate summary."""
        summary = task_boundary.current_summary()
        assert "Task Boundaries" in summary

    def test_task_boundary_list(self):
        """Should list all tasks."""
        tasks = task_boundary.list_all()
        assert isinstance(tasks, list)


class TestAsyncFeedbackModule:
    """Test async_feedback module directly."""

    def test_get_notifications_empty(self):
        """Should return empty list when no notifications."""
        notifications = async_feedback.get_notifications()
        assert isinstance(notifications, list)

    def test_add_and_check_feedback(self, tmp_path):
        """Should add and retrieve feedback."""
        import uuid
        artifact = str(tmp_path / f"test_{uuid.uuid4().hex[:8]}.md")

        # Add feedback
        async_feedback.add_feedback(artifact, "Test comment")

        # Check feedback
        comments = async_feedback.check_feedback(artifact)
        assert len(comments) >= 1
        assert "Test comment" in comments
