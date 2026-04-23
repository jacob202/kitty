"""
Tool dispatch abstraction for better error handling and logging.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class ToolDispatcher:
    def __init__(self, supervisor):
        self.supervisor = supervisor

    def execute(self, name: str, params: dict[str, Any]) -> str:
        """Execute a tool with improved error handling and logging."""
        t = self.supervisor.tools.get(name)
        if not t:
            return f"Tool '{name}' not available. Available tools: {', '.join(self.supervisor.tools.keys())}"

        try:
            # Log tool execution
            logger.info(f"Executing {name} with params: {params}")

            # Dispatch to the appropriate tool handler
            result = self._dispatch_tool(name, params, t)

            # Log successful execution
            result_preview = str(result)[:200] + "..." if len(str(result)) > 200 else str(result)
            logger.info(f"{name} executed successfully: {result_preview}")

            return result

        except Exception as e:
            error_msg = f"Tool '{name}' execution failed: {str(e)}"
            logger.error(f"{error_msg}")

            # Try to get a helpful explanation
            try:
                explain_prompt = f"Tool {name} failed with error: {str(e)[:200]}. Params: {params}. Provide a brief, helpful explanation."
                explanation = self.supervisor._call_openrouter(
                    explain_prompt,
                    "You are a helpful debugging assistant. Explain tool errors clearly.",
                    model=self.supervisor.config.get("flash_model", "google/gemini-2.0-flash-001"),
                )
                return f"{error_msg}\n\n[kitty: {explanation}]"
            except Exception:
                return error_msg

    def _dispatch_tool(self, name: str, params: dict[str, Any], tool: Any) -> str:
        """Dispatch to the specific tool implementation."""
        # SAFE COMMANDS ALLOWLIST - shell injection protection
        SAFE_SHELL_COMMANDS = {  # noqa: N806
            "git", "grep", "ls", "pwd", "cat", "head", "tail", "wc",
            "find", "xargs", "sort", "uniq", "cut", "awk", "sed",
            "python", "python3", "pip", "pip3", "node", "npm",
            "make", "cargo", "rustc", "go", "javac", "java",
            "curl", "wget", "rsync", "ssh", "scp", "tar", "gzip",
            "gunzip", "zip", "unzip", "chmod", "chown", "mkdir",
            "rmdir", "cp", "mv", "rm", "touch", "ln", "diff",
        }

        def _validate_command(cmd: str) -> tuple[bool, str]:
            """Validate command for shell injection attempts."""
            if not cmd:
                return False, "Empty command"
            # Block dangerous patterns
            dangerous = ["&&", "||", "|", ";", "$", "`", ">", "<", "\n", "\r"]
            for d in dangerous:
                if d in cmd:
                    return False, f"Disallowed: {repr(d)}"
            # Block commands that spawn shells
            banned = ["bash", "sh", "zsh", "fish", "powershell", "cmd.exe"]
            cmd_lower = cmd.strip().split()[0] if cmd.strip() else ""
            if cmd_lower in banned:
                return False, f"Shell spawn not allowed: {cmd_lower}"
            # Extract base command and check allowlist
            base_cmd = cmd.strip().split()[0] if cmd.strip() else ""
            # Handle quoted commands
            base_cmd = base_cmd.strip("'\"").split("/")[-1]
            if base_cmd and base_cmd not in SAFE_SHELL_COMMANDS:
                return False, f"Command not in allowlist: {base_cmd}"
            return True, ""

        # Handle common tools
        if name == "shell_exec":
            cmd = params.get("command") or params.get("cmd") or ""
            if not cmd:
                return "No command provided"
            # Validate command before execution
            is_valid, error_msg = _validate_command(cmd)
            if not is_valid:
                return f"Command rejected: {error_msg}"
            return tool.execute(cmd, confirm_func=self.supervisor._confirm)
        elif name == "file_read":
            path = params.get("path", "").strip()
            if not path:
                return "No path provided"
            return tool.read(path, params.get("max_lines", 150))
        elif name == "file_write":
            path = params.get("path", "")
            content = params.get("content", "")
            return tool.write(path, content, confirm_func=self.supervisor._confirm)
        elif name == "web_search":
            query = params.get("query") or " ".join(str(v) for v in params.values())
            return tool.search(query)
        elif name == "deep_search":
            # Handle deep_search which is a tuple (TavilyClient, deep_search, format_for_llm)
            if isinstance(tool, tuple) and len(tool) == 3:
                _tc, _ds, _fmt = tool
                query = params.get("query") or " ".join(str(v) for v in params.values())
                max_results = params.get("max_results", 5)
                scrape = params.get("scrape", True)
                raw = _ds(query, _tc, max_results=max_results, scrape=scrape)
                return _fmt(raw)
            else:
                return "Deep search tool not properly configured"
        elif name == "library_search":
            query = params.get("query") or " ".join(str(v) for v in params.values())
            n_results = params.get("n_results", 3)
            return tool.query(query, n_results=n_results)
        elif name == "image_gen":
            prompt = params.get("prompt") or params.get("text") or ""
            if not prompt:
                return "No prompt provided for image generation"
            return tool.generate(prompt=prompt)
        elif name == "scrape_webpage":
            url = params.get("url") or ""
            if not url:
                return "No URL provided"
            return tool(url)
        elif name == "calendar_list":
            days = params.get("days_ahead", 7)
            return tool.list_events(days)
        elif name == "calendar_create":
            title = params.get("title", "")
            start = params.get("start", "")
            duration = params.get("duration_minutes", 60)
            calendar = params.get("calendar", "")
            notes = params.get("notes", "")
            return tool.create_event(title, start, duration, calendar, notes)
        elif name == "messages_send":
            to = params.get("to", "")
            text = params.get("text", "")
            return tool.send(to, text, confirm_func=self.supervisor._confirm)
        elif name == "obsidian_read":
            path = params.get("path", "")
            return tool.read_note(path)
        elif name == "obsidian_create":
            path = params.get("path", "")
            content = params.get("content", "")
            return tool.create_note(path, content)
        elif name == "obsidian_append":
            path = params.get("path", "")
            content = params.get("content", "")
            return tool.append_note(path, content)
        elif name == "obsidian_search":
            query = params.get("query", "")
            return tool.search_notes(query)
        elif name == "obsidian_list":
            folder = params.get("folder", "")
            return tool.list_notes(folder)
        elif name == "code_read":
            path = params.get("path", "")
            return tool(path)
        elif name == "code_write":
            path = params.get("path", "")
            content = params.get("content", "")
            confirmed = params.get("confirmed", False)
            return tool(path, content, confirmed)
        elif name == "code_ls":
            subdir = params.get("subdir", params.get("path", ""))
            return tool(subdir)
        elif name == "agent_patch":
            agent = params.get("agent", "")
            field = params.get("field", "")
            operation = params.get("operation", "set")
            value = params.get("value", "")
            return tool(agent, field, operation, value)
        elif name == "obd_list":
            vin = params.get("vin")
            if not vin:
                return "Error: 'vin' parameter is required for obd_list"
            limit = params.get("limit", 10)
            return str(tool(vin, limit))
        elif name == "obd_latest":
            vin = params.get("vin")
            if not vin:
                return "Error: 'vin' parameter is required for obd_latest"
            result = str(tool(vin))
            self.supervisor._obd_auto_summary(result)
            return result
        elif name == "obd_trend":
            vin = params.get("vin")
            if not vin:
                return "Error: 'vin' parameter is required for obd_trend"
            last_n = params.get("last_n", 10)
            result = str(tool(vin, last_n))
            self.supervisor._obd_auto_summary(str(result))
            return result
        elif name == "obd_analyze":
            path = params.get("path", "")
            return str(tool(path))
        else:
            # For other tools, try to call with params
            try:
                return tool(**params)
            except TypeError:
                # Try calling without params
                try:
                    return tool()
                except Exception as e:
                    return f"Tool '{name}' execution error: {str(e)}"
