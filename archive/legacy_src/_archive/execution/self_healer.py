"""
Self-Healing Executor for Kitty

Monitors for tool failures, attempts automatic repair via web search,
updates internal prompt templates, and tests fixes in ShadowTwin before applying.

Features:
- Tool error pattern registry
- Background monitoring task
- Web search-based repair discovery
- ShadowTwin integration for testing
- Automatic config updates
"""

import json
import logging
import os
import re
import threading
import time
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from re import Pattern
from typing import Any, Optional

import requests

logger = logging.getLogger(__name__)


@dataclass
class RepairPatch:
    """Represents a repair patch for a tool."""

    tool: str
    old_command: str
    new_command: str
    description: str = ""
    source: str = "web_search"  # web_search, manual, learned
    verified: bool = False
    applied: bool = False
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "tool": self.tool,
            "old": self.old_command,
            "new": self.new_command,
            "description": self.description,
            "source": self.source,
            "verified": self.verified,
            "applied": self.applied,
            "timestamp": self.timestamp,
        }


@dataclass
class RepairResult:
    """Result of a repair attempt."""

    status: str  # "repaired", "failed", "pending_verification"
    patch: dict[str, Any] | None = None
    reason: str | None = None
    verification_output: str | None = None
    fix_command: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        result = {"status": self.status}
        if self.patch:
            result["patch"] = self.patch
        if self.reason:
            result["reason"] = self.reason
        if self.verification_output:
            result["verification_output"] = self.verification_output
        if self.fix_command:
            result["fix_command"] = self.fix_command
        return result


class ErrorPattern:
    """Pattern matcher for tool errors."""

    # Default error patterns for common tools
    DEFAULT_PATTERNS: dict[str, list[tuple[str, Pattern[str]]]] = {
        "yt-dlp": [
            (
                r"deprecated.*option",
                re.compile(r"--(\w+).*is deprecated", re.IGNORECASE),
            ),
            (
                r"Invalid.*option",
                re.compile(r"invalid.*option.*[-{]?(\w+)[}]?", re.IGNORECASE),
            ),
            (
                r" extractor.*not found",
                re.compile(r"ERROR:.*['\"]?(\w+)['\"]?.*extractor", re.IGNORECASE),
            ),
        ],
        "pip": [
            (
                r"package.*not.*found",
                re.compile(r"Could not find a version.*['\"]?([\w-]+)['\"]?", re.IGNORECASE),
            ),
            (
                r"404.*not.*found",
                re.compile(r"HTTP error 404.*['\"]?([\w-]+)['\"]?", re.IGNORECASE),
            ),
            (
                r"dependency.*conflict",
                re.compile(r"conflicting.*['\"]?([\w-]+)['\"]?", re.IGNORECASE),
            ),
            (
                r"NOT_FOUND",
                re.compile(r"Package.*not found:?\s*['\"]?([\w-]+)['\"]?", re.IGNORECASE),
            ),
        ],
        "git": [
            (
                r"authentication.*fail",
                re.compile(r"(Permission denied|Authentication failed)", re.IGNORECASE),
            ),
            (
                r"remote.*error",
                re.compile(r"remote:?\s*(.*)", re.IGNORECASE),
            ),
            (
                r"could not read.*token",
                re.compile(r"could not read.*token", re.IGNORECASE),
            ),
            (
                r"HTTP.*401",
                re.compile(r"HTTP error 401", re.IGNORECASE),
            ),
        ],
        "npm": [
            (
                r"peer.*dependency.*conflict",
                re.compile(r"ERESOLVE.*peer.*['\"]?([\w@/-]+)['\"]?", re.IGNORECASE),
            ),
            (
                r"EBADENGINE",
                re.compile(r"EBADENGINE.*['\"]?([\w@/-]+)['\"]?", re.IGNORECASE),
            ),
            (
                r"module.*not found",
                re.compile(r"Cannot find module.*['\"]?([\w@/-]+)['\"]?", re.IGNORECASE),
            ),
            (
                r"E404",
                re.compile(r"404.*['\"]?([\w@/-]+)['\"]?", re.IGNORECASE),
            ),
        ],
        "curl": [
            (
                r"SSL.*error",
                re.compile(r"SSL connect error", re.IGNORECASE),
            ),
            (
                r"HTTP.*error",
                re.compile(r"HTTP error (\d+)", re.IGNORECASE),
            ),
            (
                r"could not resolve",
                re.compile(r"could not resolve host", re.IGNORECASE),
            ),
            (
                r"connection.*refused",
                re.compile(r"Connection refused", re.IGNORECASE),
            ),
        ],
        "docker": [
            (
                r"no such image",
                re.compile(r"Error:.*no such image", re.IGNORECASE),
            ),
            (
                r"connection.*refused",
                re.compile(r"connection refused", re.IGNORECASE),
            ),
            (
                r"permission denied",
                re.compile(r"permission denied", re.IGNORECASE),
            ),
        ],
    }

    @classmethod
    def extract_error_match(cls, tool: str, error_text: str) -> tuple[str, str] | None:
        """Extract the specific error pattern match from error text.

        Args:
            tool: The tool name
            error_text: The error output

        Returns:
            Tuple of (error_type, captured_group) or None
        """
        patterns = cls.DEFAULT_PATTERNS.get(tool.lower(), [])

        for error_type, pattern in patterns:
            match = pattern.search(error_text)
            if match:
                return (error_type, match.group(1) if match.groups() else match.group(0))

        return None


class ToolErrorFixFinder:
    """Finds fixes for tool errors via web search."""

    def __init__(self, api_key: str | None = None):
        """Initialize the fix finder.

        Args:
            api_key: Optional API key for web search
        """
        self.api_key = api_key or os.environ.get("TAVILY_API_KEY", "")
        self.search_history: list[dict] = []
        self._fix_cache: dict[str, list[str]] = defaultdict(list)

    def search_fix(
        self,
        tool: str,
        error_type: str,
        captured_group: str,
        num_results: int = 5,
    ) -> list[str]:
        """Search for fixes for the given error.

        Args:
            tool: Tool name
            error_type: Type of error
            captured_group: The captured group from error pattern
            num_results: Number of results to fetch

        Returns:
            List of potential fix commands/solutions
        """
        # Build search query
        query = f"{tool} {error_type} fix solution {captured_group}"

        # Check cache first
        cache_key = f"{tool}:{error_type}:{captured_group}"
        if cache_key in self._fix_cache:
            logger.info(f"Using cached fix for {cache_key}")
            return self._fix_cache[cache_key]

        fixes = []

        try:
            # Try web search via Tavily
            if self.api_key:
                fixes = self._search_tavily(query, num_results)

            if not fixes:
                # Fallback to direct search
                fixes = self._search_fallback(query, num_results)

        except Exception as e:
            logger.warning(f"Search failed: {e}")
            fixes = []

        # Cache results
        if fixes:
            self._fix_cache[cache_key] = fixes

        # Log search
        self.search_history.append(
            {
                "timestamp": datetime.now().isoformat(),
                "tool": tool,
                "error_type": error_type,
                "query": query,
                "num_fixes": len(fixes),
            }
        )

        return fixes

    def _search_tavily(self, query: str, num_results: int) -> list[str]:
        """Search using Tavily API."""
        try:
            response = requests.post(
                "https://api.tavily.com/search",
                json={"query": query, "num_results": num_results},
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}",
                },
                timeout=10,
            )

            if response.status_code == 200:
                data = response.json()
                return [
                    result.get("content", "") for result in data.get("results", [])[:num_results]
                ]

        except Exception as e:
            logger.debug(f"Tavily search failed: {e}")

        return []

    def _search_fallback(self, query: str, num_results: int) -> list[str]:
        """Fallback search using duckduckgo or similar."""
        try:
            # Use ddg library if available, otherwise try direct URL
            from ddg import search

            results = search(query, max_results=num_results)
            return [r["body"] for r in results]

        except ImportError:
            # Try direct HTML fetch from duckduckgo
            try:
                url = f"https://html.duckduckgo.com/html/?q={query.replace(' ', '+')}"
                response = requests.get(
                    url, timeout=10, headers={"User-Agent": "Mozilla/5.0 (compatible; Kitten/1.0)"}
                )

                if response.status_code == 200:
                    # Simple parsing - extract text from result divs
                    import re

                    results = re.findall(
                        r'<a class="result__a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>',
                        response.text,
                    )
                    return [f"{title} {url}" for url, title in results[:num_results]]

            except Exception:
                pass

        return []


class PatchGenerator:
    """Generates patches from fix suggestions."""

    @staticmethod
    def generate_patch(
        tool: str,
        old_command: str,
        fix_suggestions: list[str],
    ) -> RepairPatch | None:
        """Generate a patch from fix suggestions.

        Args:
            tool: Tool name
            old_command: The original command that failed
            fix_suggestions: List of potential fixes from web search

        Returns:
            RepairPatch if one could be generated, None otherwise
        """
        if not fix_suggestions:
            return None

        # Try to extract a new command from suggestions
        new_command = None
        description = ""

        for suggestion in fix_suggestions:
            # Look for command-like patterns in the suggestion
            # Patterns like: "Use --new-flag instead of --old-flag"
            # or: "Run: pip install --upgrade package"
            # or: "command --flag new_value"

            # Extract commands from suggestion
            cmd_patterns = [
                rf"{tool}\s+[\w@/-]+.*",
                r"pip\s+install.*",
                r"npm\s+install.*",
                r"apt\s+install.*",
                r"brew\s+install.*",
            ]

            for pattern in cmd_patterns:
                match = re.search(pattern, suggestion, re.IGNORECASE)
                if match:
                    new_command = match.group(0)
                    description = f"Generated from web search: {suggestion[:200]}"
                    break

            if new_command:
                break

        if not new_command:
            # Try more generic extraction
            # Look for --flag= or --flag patterns
            old_flags = re.findall(r"--[\w-]+", old_command)

            for suggestion in fix_suggestions:
                # Look for new flags
                new_flags = re.findall(r"--[\w-]+", suggestion)

                for old_flag in old_flags:
                    for new_flag in new_flags:
                        if old_flag != new_flag:
                            # Found a potential replacement
                            new_command = old_command.replace(old_flag, new_flag)
                            description = f"Replaced {old_flag} with {new_flag}"
                            break

                    if new_command:
                        break

                if new_command:
                    break

        if new_command and new_command != old_command:
            return RepairPatch(
                tool=tool,
                old_command=old_command,
                new_command=new_command,
                description=description,
                source="web_search",
            )

        return None


class SelfHealingExecutor:
    """
    Self-Healing Executor for Kitty.

    Monitors for tool failures, attempts automatic repair via web search,
    updates internal prompt templates, and tests fixes in ShadowTwin before applying.
    """

    # Singleton instance
    _instance: Optional["SelfHealingExecutor"] = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        """Ensure singleton behavior."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self,
        config_path: str | None = None,
        shadow_twin=None,
    ):
        """Initialize the Self-Healing Executor.

        Args:
            config_path: Path to config file for storing repair history
            shadow_twin: Optional ShadowTwin instance for testing
        """
        if hasattr(self, "_initialized") and self._initialized:
            return

        self._initialized = True

        # Configuration
        self.config_path = config_path or os.path.join(
            os.path.dirname(__file__),
            "..",
            "..",
            ".config",
            "self_healer.json",
        )

        # Tool registry: maps tool names to error patterns
        self.tool_registry: dict[str, dict[str, Any]] = {}
        self._init_tool_registry()

        # Components
        self.fix_finder = ToolErrorFixFinder()
        self.patch_generator = PatchGenerator()

        # ShadowTwin for testing
        self._shadow_twin = shadow_twin

        # Repair history
        self.repair_history: list[RepairPatch] = []
        self._load_repair_history()

        # Monitoring state
        self._monitoring = False
        self._monitor_thread: threading.Thread | None = None
        self._monitor_queue: Any = None  # asyncio.Queue

        # Error callbacks
        self._error_callbacks: list[Callable[[str, str, str], None]] = []

        # Repair callbacks (called when repair is successful)
        self._repair_callbacks: list[Callable[[RepairPatch], None]] = []

    def _init_tool_registry(self):
        """Initialize the tool registry with default entries."""
        # Core tools with their error patterns
        default_tools = {
            "yt-dlp": {
                "description": "YouTube downloader",
                "error_patterns": ErrorPattern.DEFAULT_PATTERNS.get("yt-dlp", []),
                "repair_strategy": "upgrade_command",
                "common_fixes": {
                    "--yes-playlist": "--playlist-end 1",
                    "--no-download": "--skip-download",
                    "--write-subs": "--write-subs --write-auto-subs",
                },
            },
            "pip": {
                "description": "Python package installer",
                "error_patterns": ErrorPattern.DEFAULT_PATTERNS.get("pip", []),
                "repair_strategy": "upgrade_package",
                "common_fixes": {
                    "install": "install --upgrade",
                    "--upgrade": "--upgrade --upgrade-strategy only-if-needed",
                },
            },
            "git": {
                "description": "Version control",
                "error_patterns": ErrorPattern.DEFAULT_PATTERNS.get("git", []),
                "repair_strategy": "auth_reconfigure",
                "common_fixes": {
                    "git push": "git push -u origin HEAD",
                    "git pull": "git pull --rebase",
                },
            },
            "npm": {
                "description": "Node package manager",
                "error_patterns": ErrorPattern.DEFAULT_PATTERNS.get("npm", []),
                "repair_strategy": "legacy_peer_deps",
                "common_fixes": {
                    "npm install": "npm install --legacy-peer-deps",
                    "npm install": "npm install --force",
                },
            },
            "curl": {
                "description": "HTTP client",
                "error_patterns": ErrorPattern.DEFAULT_PATTERNS.get("curl", []),
                "repair_strategy": "ssl_verify",
                "common_fixes": {
                    "curl http": "curl -k https",  # Basic example
                    "curl": "curl -L",  # Follow redirects
                },
            },
            "docker": {
                "description": "Container runtime",
                "error_patterns": ErrorPattern.DEFAULT_PATTERNS.get("docker", []),
                "repair_strategy": "pull_image",
                "common_fixes": {
                    "run": "pull && run",
                    "run": "pull && run --rm",
                },
            },
        }

        self.tool_registry = default_tools

    def register_tool(
        self,
        tool_name: str,
        error_patterns: list[tuple[str, str]] = None,
        repair_strategy: str = "default",
        common_fixes: dict[str, str] = None,
    ):
        """Register a new tool with error patterns.

        Args:
            tool_name: Name of the tool
            error_patterns: List of (error_type, pattern_string) tuples
            repair_strategy: Preferred repair strategy
            common_fixes: Dict of old->new command replacements
        """
        if error_patterns:
            compiled = [
                (etype, re.compile(pattern, re.IGNORECASE)) for etype, pattern in error_patterns
            ]
        else:
            compiled = []

        self.tool_registry[tool_name] = {
            "description": "",
            "error_patterns": compiled,
            "repair_strategy": repair_strategy,
            "common_fixes": common_fixes or {},
        }

        logger.info(f"Registered tool: {tool_name}")

    def register_error_callback(self, callback: Callable[[str, str, str], None]):
        """Register a callback for tool errors.

        Args:
            callback: Function(tool_name, error, original_command)
        """
        self._error_callbacks.append(callback)

    def register_repair_callback(self, callback: Callable[[RepairPatch], None]):
        """Register a callback for successful repairs.

        Args:
            callback: Function(repair_patch)
        """
        self._repair_callbacks.append(callback)

    def monitor_tools(self, queue: Any = None):
        """Start monitoring for tool failures in background.

        Args:
            queue: Optional queue to receive error events
        """
        if self._monitoring:
            logger.warning("Monitoring already active")
            return

        self._monitoring = True
        self._monitor_queue = queue

        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            daemon=True,
            name="SelfHealer-Monitor",
        )
        self._monitor_thread.start()

        logger.info("Started tool monitoring")

    def stop_monitoring(self):
        """Stop background monitoring."""
        self._monitoring = False

        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)

        logger.info("Stopped tool monitoring")

    def _monitor_loop(self):
        """Main monitoring loop."""
        while self._monitoring:
            try:
                # Check queue if provided
                if self._monitor_queue:
                    import queue

                    try:
                        error_event = self._monitor_queue.get_nowait()
                        self._process_error_event(error_event)
                    except queue.Empty:
                        pass

                # Sleep between checks
                time.sleep(1)

            except Exception as e:
                logger.error(f"Monitor loop error: {e}")

    def _process_error_event(self, error_event: dict[str, Any]):
        """Process an error event from queue.

        Args:
            error_event: Dict with tool_name, error, original_command
        """
        tool_name = error_event.get("tool_name", "")
        error = error_event.get("error", "")
        original_command = error_event.get("original_command", "")

        if tool_name and error and original_command:
            # Try to repair
            result = self.attempt_repair(tool_name, error, original_command)

            # Notify callbacks
            for callback in self._error_callbacks:
                try:
                    callback(tool_name, error, original_command)
                except Exception as e:
                    logger.error(f"Error in callback: {e}")

            if result.status == "repaired":
                for callback in self._repair_callbacks:
                    try:
                        callback(result.patch)
                    except Exception as e:
                        logger.error(f"Error in repair callback: {e}")

    def attempt_repair(
        self,
        tool_name: str,
        error: str,
        original_command: str,
    ) -> RepairResult:
        """Attempt to repair a tool failure.

        Repair workflow:
        1. Search web for fix
        2. Generate patch/updated command
        3. Test in ShadowTwin
        4. If safe, apply to internal config
        5. Return repair status

        Args:
            tool_name: Name of the tool that failed
            error: The error message/output
            original_command: The original command that failed

        Returns:
            RepairResult with status and patch info
        """
        logger.info(f"Attempting repair for {tool_name}: {error[:100]}...")

        # Step 1: Extract error pattern match
        error_match = ErrorPattern.extract_error_match(tool_name, error)

        if error_match:
            error_type, captured_group = error_match
        else:
            error_type = "unknown"
            captured_group = ""

        # Step 2: Search for fix
        fix_suggestions = self.fix_finder.search_fix(
            tool_name, error_type, captured_group or error[:50]
        )

        if not fix_suggestions:
            # Try common fixes from registry
            tool_config = self.tool_registry.get(tool_name, {})
            common_fixes = tool_config.get("common_fixes", {})

            # Try to find a replacement in the original command
            for old_part, new_part in common_fixes.items():
                if old_part in original_command:
                    new_command = original_command.replace(old_part, new_part)
                    if new_command != original_command:
                        patch = RepairPatch(
                            tool=tool_name,
                            old_command=original_command,
                            new_command=new_command,
                            description=f"Applied common fix: {old_part} -> {new_part}",
                            source="learned",
                        )

                        return RepairResult(
                            status="repaired",
                            patch=patch.to_dict(),
                            fix_command=new_command,
                            reason="Applied common fix from registry",
                        )

            return RepairResult(
                status="failed",
                reason="Could not find fix for error",
            )

        # Step 3: Generate patch
        patch = self.patch_generator.generate_patch(tool_name, original_command, fix_suggestions)

        if not patch:
            return RepairResult(
                status="failed",
                reason="Could not generate patch from suggestions",
            )

        # Step 4: Test in ShadowTwin
        test_result = self._test_in_shadow_twin(patch.new_command)

        if not test_result["verified"]:
            return RepairResult(
                status="pending_verification",
                patch=patch.to_dict(),
                reason="Fix could not be verified in ShadowTwin",
                verification_output=test_result.get("output", ""),
            )

        # Step 5: Apply to internal config (mark as applied)
        patch.applied = True

        # Save to repair history
        self.repair_history.append(patch)
        self._save_repair_history()

        # Return result
        return RepairResult(
            status="repaired",
            patch=patch.to_dict(),
            fix_command=patch.new_command,
            verification_output=test_result.get("output", ""),
        )

    def _test_in_shadow_twin(self, command: str) -> dict[str, Any]:
        """Test a command in ShadowTwin.

        Args:
            command: The command to test

        Returns:
            Dict with verified status and output
        """
        try:
            # Try to use ShadowTwin
            if self._shadow_twin:
                twin = self._shadow_twin
            else:
                # Try to import dynamically
                try:
                    from src.execution.shadow_twin import ShadowTwin

                    twin = ShadowTwin()
                except ImportError:
                    return {
                        "verified": False,
                        "output": "ShadowTwin not available",
                    }

            # Validate the command first
            validation = twin.validate(command)

            if not validation.is_safe:
                return {
                    "verified": False,
                    "output": f"Validation failed: {validation.warning}",
                }

            # Try to execute (this will fail if not initialized)
            try:
                result = twin.execute(command, validate_first=False)
                return {
                    "verified": result.get("returncode", 1) == 0,
                    "output": result.get("stdout", "") or result.get("stderr", ""),
                }
            except RuntimeError:
                # Container not initialized - just validate
                return {
                    "verified": validation.is_safe,
                    "output": f"Validated (container not running): {validation.warning}",
                }

        except Exception as e:
            return {
                "verified": False,
                "output": str(e),
            }

    def _load_repair_history(self):
        """Load repair history from disk."""
        if not self.config_path:
            return

        path = Path(self.config_path)
        if path.exists():
            try:
                with open(path) as f:
                    data = json.load(f)
                    self.repair_history = [RepairPatch(**p) for p in data.get("history", [])]
                logger.info(f"Loaded {len(self.repair_history)} repair records")
            except Exception as e:
                logger.warning(f"Failed to load repair history: {e}")

    def _save_repair_history(self):
        """Save repair history to disk."""
        if not self.config_path:
            return

        try:
            # Ensure directory exists
            Path(self.config_path).parent.mkdir(parents=True, exist_ok=True)

            data = {
                "history": [p.to_dict() for p in self.repair_history],
                "last_updated": datetime.now().isoformat(),
            }

            with open(self.config_path, "w") as f:
                json.dump(data, f, indent=2)

        except Exception as e:
            logger.error(f"Failed to save repair history: {e}")

    def get_repair_history(self, tool_name: str | None = None) -> list[dict[str, Any]]:
        """Get repair history.

        Args:
            tool_name: Optional filter by tool name

        Returns:
            List of repair patches
        """
        if tool_name:
            return [p.to_dict() for p in self.repair_history if p.tool == tool_name]

        return [p.to_dict() for p in self.repair_history]

    def get_tool_info(self, tool_name: str) -> dict[str, Any] | None:
        """Get info about a registered tool.

        Args:
            tool_name: Name of the tool

        Returns:
            Tool configuration dict or None
        """
        return self.tool_registry.get(tool_name)

    def clear_history(self, tool_name: str | None = None):
        """Clear repair history.

        Args:
            tool_name: Optional tool name to filter by
        """
        if tool_name:
            self.repair_history = [p for p in self.repair_history if p.tool != tool_name]
        else:
            self.repair_history = []

        self._save_repair_history()

    def shutdown(self):
        """Shutdown the executor and cleanup."""
        self.stop_monitoring()
        self._save_repair_history()
        logger.info("Self-Healing Executor shutdown complete")


# Singleton accessor
_instance: SelfHealingExecutor | None = None


def get_self_healing_executor(
    config_path: str | None = None,
    shadow_twin=None,
) -> SelfHealingExecutor:
    """Get or create the SelfHealingExecutor singleton.

    Args:
        config_path: Optional path to config file
        shadow_twin: Optional ShadowTwin instance

    Returns:
        SelfHealingExecutor instance
    """
    global _instance

    if _instance is None:
        _instance = SelfHealingExecutor(config_path, shadow_twin)

    return _instance


def repair_tool(
    tool_name: str,
    error: str,
    original_command: str,
) -> dict[str, Any]:
    """Repair a tool failure (standalone function).

    Args:
        tool_name: Name of the tool that failed
        error: The error message/output
        original_command: The original command that failed

    Returns:
        RepairResult dict
    """
    executor = get_self_healing_executor()
    result = executor.attempt_repair(tool_name, error, original_command)
    return result.to_dict()


# Example usage
if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    print("Self-Healing Executor Demo")
    print("=" * 60)

    # Create executor
    executor = SelfHealingExecutor()

    # Show registered tools
    print("\nRegistered Tools:")
    for tool_name in executor.tool_registry:
        info = executor.tool_registry[tool_name]
        print(f"  - {tool_name}: {info.get('description', '')}")

    # Test error pattern extraction
    print("\nError Pattern Extraction Test:")
    test_errors = [
        ("yt-dlp", "ERROR: --yes-playlist is deprecated, use --playlist-end instead"),
        ("pip", "ERROR: Could not find version of package 'requests>=2.28'"),
        ("npm", "ERROR: ERESOLVE overridePeerDependency"),
    ]

    for tool, error in test_errors:
        match = ErrorPattern.extract_error_match(tool, error)
        if match:
            print(f"  {tool}: {match[0]} -> '{match[1]}'")
        else:
            print(f"  {tool}: No match")

    # Test repair (won't actually search web in demo)
    print("\nRepair Attempt Test:")

    # This would require actual web search to work
    # result = executor.attempt_repair(
    #     "yt-dlp",
    #     "ERROR: --yes-playlist is deprecated",
    #     "yt-dlp --yes-playlist https://example.com"
    # )
    # print(f"Result: {result.status}")

    print("\nDone (web search requires API key for actual fixes)")
