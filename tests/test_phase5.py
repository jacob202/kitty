"""Tests for plugin_registry, mcp_tool_bridge, cron."""
import pytest
from unittest.mock import patch


class TestPluginRegistry:
    def test_register_and_list(self):
        from gateway.plugin_registry import register, list_plugins, reset
        reset()
        register("test-plugin", "A test plugin", skills=[{"name": "test-skill"}])
        plugins = list_plugins()
        assert any(p["name"] == "test-plugin" for p in plugins)

    def test_double_register_returns_false(self):
        from gateway.plugin_registry import register, reset
        reset()
        assert register("unique", "desc") is True
        assert register("unique", "desc") is False

    def test_enable_disable(self):
        from gateway.plugin_registry import register, enable, disable, is_enabled, reset
        reset()
        register("toggle", "toggle test", default_enabled=True)
        assert is_enabled("toggle") is True
        assert disable("toggle") is True
        assert is_enabled("toggle") is False
        assert enable("toggle") is True
        assert is_enabled("toggle") is True

    def test_nonexistent_enable(self):
        from gateway.plugin_registry import enable, disable
        assert enable("nope") is False
        assert disable("nope") is False

    def test_get_enabled_skills(self):
        from gateway.plugin_registry import register, get_enabled_skills, reset
        reset()
        register("p1", skills=[{"name": "skill-a"}, {"name": "skill-b"}])
        skills = get_enabled_skills()
        assert len(skills) == 2

    def test_get_enabled_mcp_servers(self):
        from gateway.plugin_registry import register, get_enabled_mcp_servers, reset
        reset()
        register("p1", mcp_servers=[{"name": "filesystem", "tools": []}])
        servers = get_enabled_mcp_servers()
        assert len(servers) == 1

    def test_is_available_filter(self):
        from gateway.plugin_registry import register, list_plugins, reset
        reset()
        register("present", is_available=lambda: True)
        register("absent", is_available=lambda: False)
        plugins = list_plugins()
        names = {p["name"] for p in plugins}
        assert "present" in names
        assert "absent" not in names


class TestMCPBridge:
    def test_list_servers(self):
        from gateway.mcp_tool_bridge import list_servers
        servers = list_servers()
        assert isinstance(servers, list)

    def test_get_tool_schema(self):
        from gateway.mcp_tool_bridge import get_tool_schema_for_llm
        tools = get_tool_schema_for_llm()
        assert isinstance(tools, list)

    def test_list_tools_empty(self):
        from gateway.mcp_tool_bridge import list_tools
        assert list_tools("nonexistent") == []


class TestCron:
    def test_schedule_and_list(self):
        from gateway.cron import schedule, list_schedules, init_db
        init_db()
        sid = schedule("test", "brief", "daily", "07:00")
        assert len(sid) == 8
        schedules = list_schedules()
        assert any(s["name"] == "test" for s in schedules)

    def test_remove(self):
        from gateway.cron import schedule, remove, init_db
        init_db()
        sid = schedule("temp", "brief", "once", "2099-01-01T00:00")
        assert remove(sid) is True
        assert remove(sid) is False

    def test_register_action(self):
        from gateway.cron import register_action
        called = []
        async def my_action():
            called.append(True)
        register_action("my_action", my_action)
        from gateway.cron import _actions
        assert "my_action" in _actions

    def test_should_fire_interval(self):
        from gateway.cron import _should_fire
        import time
        s = {"last_run": time.time() - 3600, "schedule_type": "interval", "schedule_value": "30"}
        assert _should_fire(s, time.time()) is True

    def test_should_fire_not_yet(self):
        from gateway.cron import _should_fire
        import time
        s = {"last_run": time.time(), "schedule_type": "interval", "schedule_value": "9999"}
        assert _should_fire(s, time.time()) is False
