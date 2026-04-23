"""
Modular tool registry for the supervisor system.
"""
from typing import Any

from src.utils.cli_helpers import p_success, p_warn


class ToolRegistry:
    def __init__(self, supervisor):
        self.supervisor = supervisor
        self.config = supervisor.config
        self.tools: dict[str, Any] = {}

    def initialize_all(self) -> dict[str, Any]:
        """Initialize all tools and return the tools dictionary."""
        self._init_web_tools()
        self._init_multimedia_tools()
        self._init_system_tools()
        self._init_domain_tools()
        self._init_custom_tools()

        p_success(f"Tools ready: {', '.join(self.tools.keys())}")
        return self.tools

    def _init_web_tools(self):
        if self.config.get("tavily_api_key"):
            try:
                from tools.web_search import WebSearch
                self.tools["web_search"] = WebSearch(self.config["tavily_api_key"])
            except Exception as e:
                p_warn(f"web_search: {e}")
                class DummyWebSearch:
                    def search(self, *args, **kwargs):
                        return "Web search not available (tavily-python not installed)"
                self.tools["web_search"] = DummyWebSearch()

            try:
                from tavily import TavilyClient

                from tools.deep_search import deep_search, format_for_llm
                _tc = TavilyClient(api_key=self.config["tavily_api_key"])
                self.tools["deep_search"] = (_tc, deep_search, format_for_llm)
            except Exception as e:
                p_warn(f"deep_search: {e}")
                class DummyDeepSearch:
                    def __call__(self, *args, **kwargs):
                        return {"error": "Deep search not available (tavily not installed)"}
                self.tools["deep_search"] = (None, DummyDeepSearch(), lambda x: "Deep search unavailable")

        try:
            from tools.scraper import scrape_url
            self.tools["scrape_webpage"] = scrape_url
        except Exception as e:
            p_warn(f"scraper: {e}")

    def _init_multimedia_tools(self):
        try:
            from tools.image_gen import DrawThingsGenerator
            self.tools["image_gen"] = DrawThingsGenerator(self.config.get("draw_things_base_url", "http://127.0.0.1:7859"))
        except Exception:
            pass

        if self.config.get("face_swap_enabled"):
            try:
                from tools.face_swap import FaceSwapper
                self.tools["face_swap"] = FaceSwapper()
            except Exception:
                pass

    def _init_system_tools(self):
        from tools.system_tools import (
            AppTool,
            CalendarTool,
            FileTool,
            MessagesTool,
            ObsidianTool,
            RemindersTool,
            ServerTool,
            ShellTool,
        )

        file_tool = FileTool()
        shell_tool = ShellTool()
        self.tools["file_read"] = file_tool
        self.tools["file_write"] = file_tool
        self.tools["file_list"] = file_tool
        self.tools["shell_exec"] = shell_tool

        app_tool = AppTool()
        self.tools["app_open"] = app_tool
        self.tools["app_close"] = app_tool
        self.tools["app_list"] = app_tool
        self.tools["app_script"] = app_tool

        server_tool = ServerTool()
        self.tools["server_status"] = server_tool
        self.tools["http_request"] = server_tool

        _obsidian = ObsidianTool(self.config.get("obsidian_vault_path", ""))
        self.tools["obsidian_create"] = _obsidian
        self.tools["obsidian_append"] = _obsidian
        self.tools["obsidian_read"] = _obsidian
        self.tools["obsidian_search"] = _obsidian
        self.tools["obsidian_list"] = _obsidian

        _cal = CalendarTool()
        self.tools["calendar_list"] = _cal
        self.tools["calendar_create"] = _cal

        _msg = MessagesTool()
        self.tools["messages_send"] = _msg
        self.tools["messages_recent"] = _msg

        _rem = RemindersTool()
        self.tools["reminder_create"] = _rem

    def _init_domain_tools(self):
        try:
            from tools.obd_parser import analyze_latest, analyze_log, list_logs, trend_summary
            self.tools["obd_list"] = list_logs
            self.tools["obd_latest"] = analyze_latest
            self.tools["obd_trend"] = trend_summary
            self.tools["obd_analyze"] = analyze_log
        except Exception as e:
            p_warn(f"obd_parser: {e}")

        try:
            from tools.code_edit import (
                list_kitty_files,
                patch_agent_json,
                read_kitty_file,
                write_kitty_file,
            )
            self.tools["code_read"] = read_kitty_file
            self.tools["code_write"] = write_kitty_file
            self.tools["code_ls"] = list_kitty_files
            self.tools["agent_patch"] = patch_agent_json
        except Exception as e:
            p_warn(f"code_edit: {e}")

    def _init_custom_tools(self):
        try:
            from tools.lightrag_wrapper import LightRAGWrapper
            self.tools["lightrag_search"] = LightRAGWrapper()
        except Exception as e:
            p_warn(f"lightrag_wrapper: {e}")
            class DummyLightRAGWrapper:
                def __call__(self, *args, **kwargs):
                    return "LightRAG not available (numpy not installed)"
            self.tools["lightrag_search"] = DummyLightRAGWrapper()
