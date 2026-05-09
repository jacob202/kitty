"""
Kitty Tool Framework
Function calling with safety sandbox
"""

import json
import os
import subprocess
import webbrowser
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import lru_cache
from typing import Any


@dataclass
class ToolDefinition:
    """Definition of a tool"""

    name: str
    description: str
    parameters: dict[str, Any]
    required: list[str]
    function: Callable


class KittyTools:
    """
    Tool framework for Kitty AI
    Safe, sandboxed tool execution
    """

    # Dangerous commands to block
    DANGEROUS_COMMANDS = [
        "rm",
        "del",
        "format",
        "shutdown",
        "sudo",
        "mkfs",
        "dd",
        "fdisk",
        "mount",
        "umount",
        "chmod",
        "chown",
    ]

    def __init__(self):
        self.tools: dict[str, ToolDefinition] = {}
        self._register_builtin_tools()

    def _register_builtin_tools(self):
        """Register all built-in tools"""

        # Time tool
        self.register_tool(
            name="get_current_time",
            description="Get the current time and date",
            parameters={
                "timezone": {
                    "type": "string",
                    "description": "Timezone (e.g., 'America/New_York')",
                    "default": "local",
                }
            },
            required=[],
            function=self._tool_get_time,
        )

        # Reminder tool
        self.register_tool(
            name="set_reminder",
            description="Set a reminder for the user",
            parameters={
                "message": {"type": "string", "description": "Reminder text"},
                "minutes_from_now": {"type": "integer", "description": "Minutes until reminder"},
            },
            required=["message", "minutes_from_now"],
            function=self._tool_set_reminder,
        )

        # Calculator tool
        self.register_tool(
            name="calculate",
            description="Perform a calculation",
            parameters={
                "expression": {
                    "type": "string",
                    "description": "Math expression (e.g., '2 + 2', 'sqrt(16)')",
                }
            },
            required=["expression"],
            function=self._tool_calculate,
        )

        # Web search tool
        self.register_tool(
            name="search_web",
            description="Search the web for information",
            parameters={"query": {"type": "string", "description": "Search query"}},
            required=["query"],
            function=self._tool_search_web,
        )

        # Browse tool (alias for search_web)
        self.register_tool(
            name="browse",
            description="Browse the web for information",
            parameters={"query": {"type": "string", "description": "Search query"}},
            required=["query"],
            function=self._tool_search_web,
        )

        # Weather tool (placeholder)
        self.register_tool(
            name="get_weather",
            description="Get current weather for a location",
            parameters={"city": {"type": "string", "description": "City name"}},
            required=["city"],
            function=self._tool_get_weather,
        )

        # Open application tool
        self.register_tool(
            name="open_application",
            description="Open an application",
            parameters={
                "app_name": {
                    "type": "string",
                    "description": "Application name",
                    "enum": ["browser", "calculator", "notepad", "spotify"],
                }
            },
            required=["app_name"],
            function=self._tool_open_app,
        )

        # File read tool
        self.register_tool(
            name="read_file",
            description="Read contents of a file",
            parameters={"file_path": {"type": "string", "description": "Path to file"}},
            required=["file_path"],
            function=self._tool_read_file,
        )

        # File search tool
        self.register_tool(
            name="search_files",
            description="Search for a pattern in files",
            parameters={
                "query": {"type": "string", "description": "Pattern to search for"},
                "path": {"type": "string", "description": "Directory to search in", "default": "."}
            },
            required=["query"],
            function=self._tool_search_files,
        )

        # Diagnostics tool
        self.register_tool(
            name="read_diagnostics",
            description="Read system diagnostics and logs",
            parameters={
                "component": {"type": "string", "description": "Component to check (e.g., 'orchestrator', 'memory')"}
            },
            required=[],
            function=self._tool_read_diagnostics,
        )

    def register_tool(
        self,
        name: str,
        description: str,
        parameters: dict[str, Any],
        required: list[str],
        function: Callable,
    ):
        """Register a new tool"""
        self.tools[name] = ToolDefinition(
            name=name,
            description=description,
            parameters=parameters,
            required=required,
            function=function,
        )

    @lru_cache(maxsize=1)
def _get_tool_schemas_cached(tools_tuple: tuple) -> list[dict]:
    """Cached tool schema generation"""
    # Convert tuple back to dict for computation
    tools = dict(tools_tuple)
    schemas = []
    for tool in tools.values():
        schema = {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": {
                    "type": "object",
                    "properties": tool.parameters,
                    "required": tool.required,
                },
            },
        }
        schemas.append(schema)
    return schemas


def get_tool_schemas(self) -> list[dict]:
        """Get JSON schemas for all tools (for LLM)"""
        # Use cached version for efficiency
        try:
            tools_tuple = tuple(sorted(self.tools.items()))
            return _get_tool_schemas_cached(tools_tuple)
        except TypeError:
            # Fallback if tools aren't hashable
            schemas = []
            for tool in self.tools.values():
                schema = {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": {
                            "type": "object",
                            "properties": tool.parameters,
                            "required": tool.required,
                        },
                    },
                }
                schemas.append(schema)
            return schemas

    def execute(self, tool_name: str, arguments: dict[str, Any]) -> str:
        """
        Execute a tool safely

        Args:
            tool_name: Name of tool to execute
            arguments: Arguments for the tool

        Returns:
            Result string
        """
        if tool_name not in self.tools:
            return f"❌ Unknown tool: {tool_name}"

        tool = self.tools[tool_name]

        # Validate required parameters
        for req in tool.required:
            if req not in arguments:
                return f"❌ Missing required parameter: {req}"

        try:
            # Execute tool
            result = tool.function(**arguments)
            return str(result)
        except Exception as e:
            return f"❌ Tool execution error: {str(e)}"

    def list_tools(self) -> list[str]:
        """List available tools"""
        return [f"{t.name}: {t.description}" for t in self.tools.values()]

    # === Tool Implementations ===

    def _tool_get_time(self, timezone: str = "local") -> str:
        """Get current time"""
        now = datetime.now()
        return f"Current time: {now.strftime('%Y-%m-%d %H:%M:%S')} ({timezone})"

    def _tool_set_reminder(self, message: str, minutes_from_now: int) -> str:
        """Set a reminder"""
        trigger_time = datetime.now() + timedelta(minutes=minutes_from_now)
        # In real implementation, this would schedule a notification
        return f"✅ Reminder set: '{message}' at {trigger_time.strftime('%H:%M')}"

    def _tool_calculate(self, expression: str) -> str:
        """Safe calculation"""
        # Sanitize expression
        allowed_chars = set("0123456789+-*/(). sqrtpowabsround")
        if not all(c in allowed_chars for c in expression.replace(" ", "")):
            return "❌ Invalid characters in expression"

        try:
            # Safe eval with limited scope
            result = eval(
                expression,
                {"__builtins__": {}},
                {"sqrt": lambda x: x**0.5, "pow": pow, "abs": abs, "round": round},
            )
            return f"{expression} = {result}"
        except Exception as e:
            return f"❌ Calculation error: {str(e)}"

    def _tool_search_web(self, query: str) -> str:
        """Open web search"""
        url = f"https://duckduckgo.com/?q={query.replace(' ', '+')}"
        webbrowser.open(url)
        return f"🔍 Opened search for: {query}"

    def _tool_get_weather(self, city: str) -> str:
        """Get weather (placeholder)"""
        # Would integrate with weather API
        return f"🌤️ Weather for {city}: [Weather API not configured]"

    def _tool_open_app(self, app_name: str) -> str:
        """Open application"""
        app_map = {
            "browser": "https://www.google.com",
            "calculator": "calc" if os.name == "nt" else "gnome-calculator",
            "notepad": "notepad" if os.name == "nt" else "gedit",
            "spotify": "spotify",
        }

        if app_name not in app_map:
            return f"❌ Unknown app: {app_name}"

        target = app_map[app_name]

        try:
            if target.startswith("http"):
                webbrowser.open(target)
            else:
                subprocess.Popen([target], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return f"✅ Opened {app_name}"
        except Exception as e:
            return f"❌ Could not open {app_name}: {str(e)}"

    def _tool_read_file(self, file_path: str) -> str:
        """Read file safely"""
        # Security: Check for dangerous paths
        abs_path = os.path.abspath(file_path)

        # Block access to sensitive directories
        blocked_prefixes = ["/etc", "/sys", "/proc", "/dev", "C:\\Windows"]
        for blocked in blocked_prefixes:
            if abs_path.startswith(blocked):
                return "❌ Access denied to system directory"

        try:
            with open(abs_path, encoding="utf-8", errors="ignore") as f:
                content = f.read()
                # Limit output size
                if len(content) > 2000:
                    content = content[:2000] + "\n... [truncated]"
                return content
        except Exception as e:
            return f"❌ Could not read file: {str(e)}"

    def _tool_search_files(self, query: str, path: str = ".") -> str:
        """Search files for pattern"""
        try:
            from src.tools.tool_manager import get_tool_manager
            manager = get_tool_manager()
            result = manager.execute("search_files", query=query, path=path)
            if result.ok:
                matches = result.result.get("matches", [])
                if not matches:
                    return "No matches found"
                lines = [f"{m['file']}:{m['line']}: {m['text']}" for m in matches[:10]]
                return "\n".join(lines) + ("\n... [truncated]" if len(matches) > 10 else "")
            return f"❌ Search failed: {result.error}"
        except Exception as e:
            return f"❌ Search error: {str(e)}"

    def _tool_read_diagnostics(self, component: str = "all") -> str:
        """Read diagnostics"""
        try:
            log_path = ".kitty.log"
            if os.path.exists(log_path):
                with open(log_path, "r") as f:
                    lines = f.readlines()
                    last_lines = lines[-20:]
                    return f"Last 20 lines of {log_path}:\n" + "".join(last_lines)
            return "No diagnostic logs found."
        except Exception as e:
            return f"❌ Diagnostics error: {str(e)}"


class ToolCallingLoop:
    """
    Handle tool calling conversation loop with LLM
    """

    def __init__(self, tools: KittyTools, process_callback=None):
        self.tools = tools
        self.process_callback = process_callback
        self.max_iterations = 5

    def process(self, user_input: str) -> str:
        """
        Process user input with potential tool calls

        Args:
            user_input: User's message

        Returns:
            Final response
        """
        # Get tool schemas
        tool_schemas = self.tools.get_tool_schemas()

        # Build tool-enabled prompt
        tool_prompt = self._build_tool_prompt(user_input, tool_schemas)

        # Get response from LLM
        if self.process_callback:
            response = self.process_callback(tool_prompt)
        else:
            response = self._mock_llm_response(user_input)

        # Check for tool calls
        for iteration in range(self.max_iterations):
            tool_call = self._extract_tool_call(response)

            if not tool_call:
                # No tool call, return response
                return response

            # Execute tool
            result = self.tools.execute(tool_call["name"], tool_call["arguments"])

            # Build follow-up prompt with tool result
            followup_prompt = f"""
You used tool: {tool_call["name"]}
Tool result: {result}

Now respond to the user naturally.
"""

            if self.process_callback:
                response = self.process_callback(followup_prompt)
            else:
                response = f"[Used {tool_call['name']}] {result}"

        return response

    def _build_tool_prompt(self, user_input: str, tool_schemas: list[dict]) -> str:
        """Build prompt with tool definitions"""
        schemas_text = json.dumps(tool_schemas, indent=2)

        return f"""You have access to these tools:
{schemas_text}

To use a tool, respond with:
<tool_call>
{{"name": "tool_name", "arguments": {{"param": "value"}}}}
</tool_call>

User: {user_input}
"""

    def _extract_tool_call(self, response: str) -> dict | None:
        """Extract tool call from response"""
        if "<tool_call>" not in response:
            return None

        try:
            start = response.find("<tool_call>") + len("<tool_call>")
            end = response.find("</tool_call>")

            if end == -1:
                return None

            tool_json = response[start:end].strip()
            return json.loads(tool_json)
        except Exception:
            return None

    def _mock_llm_response(self, user_input: str) -> str:
        """Mock LLM for testing"""
        # Simple pattern matching for testing
        if "time" in user_input.lower():
            return '<tool_call>{"name": "get_current_time", "arguments": {}}</tool_call>'
        elif "calculate" in user_input.lower() or "math" in user_input.lower():
            return (
                '<tool_call>{"name": "calculate", "arguments": {"expression": "2 + 2"}}</tool_call>'
            )
        else:
            return f"I received: {user_input}"


# Quick test
if __name__ == "__main__":
    print("🔧 Testing Kitty Tools\n")

    tools = KittyTools()

    print("Available tools:")
    for tool_desc in tools.list_tools():
        print(f"  • {tool_desc}")

    print("\n" + "=" * 50)

    # Test executions
    test_calls = [
        ("get_current_time", {}),
        ("set_reminder", {"message": "Call mom", "minutes_from_now": 30}),
        ("calculate", {"expression": "2 + 2 * 5"}),
        ("search_web", {"query": "python tutorial"}),
    ]

    for tool_name, args in test_calls:
        print(f"\n🔹 {tool_name}({args})")
        result = tools.execute(tool_name, args)
        print(f"   → {result}")
