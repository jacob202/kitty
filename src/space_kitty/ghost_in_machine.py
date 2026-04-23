"""
Ghost in the Machine — Zero-Click Environmental State Injection

Captures terminal state BEFORE each user query and automatically injects
invisible system headers into prompts. No user action required.

Components:
- StateInjector: Captures pwd, git status, ls, clipboard
- GhostHeader: Formats state as invisible prefix
- Privacy controls: Whitelist/blacklist, sensitive path exclusion
"""

import json
import os
import re
import shutil
import subprocess
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.core.db_config import get_db_path

# =============================================================================
# Database Setup
# =============================================================================

_DB_PATH = get_db_path("ghost_state")
_lock = threading.Lock()


def _init_db():
    """Initialize SQLite database for state history and privacy settings."""
    _DB_PATH.parent.mkdir(exist_ok=True)
    with _lock:
        import sqlite3

        with sqlite3.connect(str(_DB_PATH)) as c:
            c.execute("PRAGMA journal_mode=WAL")
            c.execute(
                """
                CREATE TABLE IF NOT EXISTS state_history (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp   TEXT NOT NULL,
                    pwd         TEXT,
                    git_branch  TEXT,
                    git_status  TEXT,
                    ls_summary  TEXT,
                    clipboard   TEXT,
                    metadata    TEXT DEFAULT '{}'
                )
            """
            )
            c.execute(
                """
                CREATE TABLE IF NOT EXISTS privacy_settings (
                    key         TEXT PRIMARY KEY,
                    value       TEXT NOT NULL,
                    updated_at  TEXT NOT NULL
                )
            """
            )
            c.execute(
                """
                CREATE TABLE IF NOT EXISTS exclusion_rules (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    rule_type   TEXT NOT NULL,  -- 'path' | 'pattern' | 'env_var'
                    pattern     TEXT NOT NULL,
                    is_active   INTEGER DEFAULT 1,
                    created_at  TEXT NOT NULL
                )
            """
            )
            c.commit()


_init_db()


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class CaptureConfig:
    """Configuration for what gets captured."""

    capture_pwd: bool = True
    capture_git: bool = True
    capture_ls: bool = True
    capture_clipboard: bool = True

    # Output limits
    ls_max_items: int = 20
    ls_max_depth: int = 1
    clipboard_max_chars: int = 500

    # Filters
    exclude_hidden: bool = True
    exclude_common_ignored: bool = True  # Exclude .gitignore'd files from ls

    def to_dict(self) -> dict:
        return {
            "capture_pwd": self.capture_pwd,
            "capture_git": self.capture_git,
            "capture_ls": self.capture_ls,
            "capture_clipboard": self.capture_clipboard,
            "ls_max_items": self.ls_max_items,
            "ls_max_depth": self.ls_max_depth,
            "clipboard_max_chars": self.clipboard_max_chars,
            "exclude_hidden": self.exclude_hidden,
            "exclude_common_ignored": self.exclude_common_ignored,
        }


@dataclass
class CapturedState:
    """Container for all captured environmental state."""

    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    # Core state
    pwd: str | None = None
    git_branch: str | None = None
    git_status: str | None = None
    git_modified_files: list[str] = field(default_factory=list)
    git_untracked_files: list[str] = field(default_factory=list)

    # Directory listing
    ls_files: list[str] = field(default_factory=list)
    ls_total_count: int = 0

    # Clipboard
    clipboard_content: str | None = None
    clipboard_has_content: bool = False

    # Metadata
    capture_duration_ms: float = 0.0
    privacy_filtered: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "pwd": self.pwd,
            "git_branch": self.git_branch,
            "git_status": self.git_status,
            "git_modified_files": self.git_modified_files,
            "git_untracked_files": self.git_untracked_files,
            "ls_files": self.ls_files,
            "ls_total_count": self.ls_total_count,
            "clipboard_content": self.clipboard_content,
            "clipboard_has_content": self.clipboard_has_content,
            "capture_duration_ms": self.capture_duration_ms,
            "privacy_filtered": self.privacy_filtered,
        }


@dataclass
class GhostHeaderData:
    """Formatted ghost header for injection."""

    compact: str = ""  # One-line compact format
    expanded: str = ""  # Multi-line expanded format
    components: dict[str, str] = field(default_factory=dict)


# =============================================================================
# Utility Functions
# =============================================================================

# Common files/dirs to exclude from ls
COMMON_IGNORED = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".tox",
    "node_modules",
    ".venv",
    "venv",
    ".env",
    ".DS_Store",
    "*.pyc",
    "*.pyo",
    "*.so",
    "*.dylib",
    ".egg-info",
    "dist",
    "build",
    ".coverage",
    ".hypothesis",
}


def _run_command(cmd: list[str], timeout: float = 2.0, cwd: str | None = None) -> str | None:
    """Run a shell command with timeout, return stdout or None on failure."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd or os.getcwd(),
        )
        return result.stdout.strip() if result.returncode == 0 else None
    except (subprocess.TimeoutExpired, FileNotFoundError, PermissionError):
        return None


def _shorten_path(path: str, home: str | None = None) -> str:
    """Shorten path by replacing home with ~."""
    if home is None:
        home = os.path.expanduser("~")
    if path.startswith(home):
        return "~" + path[len(home) :]
    return path


def _is_sensitive_path(path: str) -> bool:
    """Check if a path contains sensitive information."""
    sensitive_patterns = [
        r"/\.ssh/",
        r"/\.aws/",
        r"/\.config/",
        r"/secrets",
        r"/\.env",
        r"/password",
        r"/credential",
        r"/token",
        r"/api.?key",
        r"\.pem$",
        r"\.key$",
        r"\.crt$",
    ]
    path_lower = path.lower()
    return any(re.search(p, path_lower) for p in sensitive_patterns)


def _get_gitignored_patterns() -> set[str]:
    """Get patterns from .gitignore for filtering."""
    patterns = set(COMMON_IGNORED)
    try:
        gitignore_path = Path.cwd() / ".gitignore"
        if gitignore_path.exists():
            with open(gitignore_path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        patterns.add(line)
    except (PermissionError, FileNotFoundError):
        pass
    return patterns


def _matches_gitignore(name: str, patterns: set[str]) -> bool:
    """Check if a file/dir name matches gitignore patterns."""
    for pattern in patterns:
        if pattern.startswith("*."):
            ext = pattern[1:]
            if name.endswith(ext):
                return True
        elif pattern.endswith("/"):
            if name == pattern[:-1] or name.startswith(pattern):
                return True
        elif name == pattern:
            return True
    return False


# =============================================================================
# StateInjector Class
# =============================================================================


class StateInjector:
    """
    Captures terminal state on demand.

    Captures:
    - Current working directory
    - Git status (branch, modified files, untracked files)
    - Directory listing (filtered, limited)
    - Clipboard content (macOS pbpaste)

    Thread-safe and memoized to avoid repeated captures.
    """

    def __init__(self, config: CaptureConfig | None = None):
        self.config = config or CaptureConfig()
        self._cache: CapturedState | None = None
        self._cache_timestamp: datetime | None = None
        self._cache_ttl_seconds: float = 5.0  # Cache validity window
        self._home = os.path.expanduser("~")

        # Load privacy settings
        self._exclusion_rules: list[dict] = []
        self._load_exclusion_rules()

    def _load_exclusion_rules(self):
        """Load exclusion rules from database."""
        import sqlite3

        try:
            with sqlite3.connect(str(_DB_PATH)) as c:
                rows = c.execute(
                    "SELECT rule_type, pattern FROM exclusion_rules WHERE is_active = 1"
                ).fetchall()
                self._exclusion_rules = [{"type": r[0], "pattern": r[1]} for r in rows]
        except Exception:
            self._exclusion_rules = []

    def _should_exclude(self, path: str) -> bool:
        """Check if path should be excluded based on privacy rules."""
        if _is_sensitive_path(path):
            return True

        for rule in self._exclusion_rules:
            pattern = rule["pattern"]
            if rule["type"] == "path" and pattern in path:
                return True
            elif rule["type"] == "pattern" and re.search(pattern, path):
                return True
            elif rule["type"] == "env_var" and os.environ.get(pattern):
                env_path = os.environ.get(pattern, "")
                if env_path in path:
                    return True

        return False

    def invalidate_cache(self):
        """Clear the state cache to force fresh capture."""
        self._cache = None
        self._cache_timestamp = None

    def capture(self, force_refresh: bool = False) -> CapturedState:
        """
        Capture all environmental state.

        Args:
            force_refresh: Bypass cache and capture fresh

        Returns:
            CapturedState with all captured information
        """
        import time

        start_time = time.time()

        # Check cache validity
        if not force_refresh and self._cache is not None and self._cache_timestamp is not None:
            age = (datetime.now() - self._cache_timestamp).total_seconds()
            if age < self._cache_ttl_seconds:
                return self._cache

        # Perform captures
        state = CapturedState()
        privacy_filtered = []

        # Capture pwd
        if self.config.capture_pwd:
            pwd = os.getcwd()
            if not self._should_exclude(pwd):
                state.pwd = _shorten_path(pwd, self._home)
            else:
                privacy_filtered.append("pwd")

        # Capture git status
        if self.config.capture_git:
            git_info = self._capture_git_status()
            state.git_branch = git_info.get("branch")
            state.git_status = git_info.get("status_summary")
            state.git_modified_files = git_info.get("modified", [])
            state.git_untracked_files = git_info.get("untracked", [])
            if git_info.get("filtered"):
                privacy_filtered.extend(git_info["filtered"])

        # Capture directory listing
        if self.config.capture_ls:
            ls_info = self._capture_ls()
            state.ls_files = ls_info.get("files", [])
            state.ls_total_count = ls_info.get("total", 0)
            if ls_info.get("filtered"):
                privacy_filtered.extend(ls_info["filtered"])

        # Capture clipboard
        if self.config.capture_clipboard:
            clipboard_info = self._capture_clipboard()
            state.clipboard_content = clipboard_info.get("content")
            state.clipboard_has_content = clipboard_info.get("has_content", False)
            if clipboard_info.get("filtered"):
                privacy_filtered.append("clipboard")

        state.privacy_filtered = list(set(privacy_filtered))
        state.capture_duration_ms = (time.time() - start_time) * 1000

        # Cache result
        self._cache = state
        self._cache_timestamp = datetime.now()

        # Store in history
        self._store_state(state)

        return state

    def _capture_git_status(self) -> dict:
        """Capture git status information."""
        result = {
            "branch": None,
            "status_summary": None,
            "modified": [],
            "untracked": [],
            "filtered": [],
        }

        # Get branch
        branch = _run_command(["git", "branch", "--show-current"])
        if branch:
            result["branch"] = branch

        # Get porcelain status
        status_output = _run_command(["git", "status", "--porcelain"], timeout=3.0)

        if status_output:
            lines = status_output.split("\n")
            for line in lines:
                if not line.strip():
                    continue
                # Format: XY filename
                # X = staged, Y = working tree
                status_code = line[:2]
                filename = line[3:].strip()

                # Skip sensitive paths
                if self._should_exclude(filename):
                    result["filtered"].append(filename)
                    continue

                # Categorize
                if status_code[1] == "M":
                    result["modified"].append(filename)
                elif status_code[0] == "?":
                    result["untracked"].append(filename)
                elif status_code[1] == "?":
                    result["untracked"].append(filename)

            # Build summary
            modified_count = len(result["modified"])
            untracked_count = len(result["untracked"])
            if modified_count > 0 or untracked_count > 0:
                parts = []
                if modified_count > 0:
                    parts.append(f"{modified_count} modified")
                if untracked_count > 0:
                    parts.append(f"{untracked_count} untracked")
                result["status_summary"] = ", ".join(parts)
            else:
                result["status_summary"] = "clean"

        return result

    def _capture_ls(self) -> dict:
        """Capture directory listing with filtering."""
        result = {"files": [], "total": 0, "filtered": []}
        gitignore_patterns = _get_gitignored_patterns()

        try:
            entries = os.listdir(".")
            result["total"] = len(entries)

            count = 0
            for entry in entries:
                if count >= self.config.ls_max_items:
                    break

                # Skip hidden if configured
                if self.config.exclude_hidden and entry.startswith("."):
                    continue

                # Skip gitignore'd patterns
                if self.config.exclude_common_ignored and _matches_gitignore(
                    entry, gitignore_patterns
                ):
                    result["filtered"].append(entry)
                    continue

                # Check privacy filter
                if self._should_exclude(entry):
                    result["filtered"].append(entry)
                    continue

                # Get file type indicator
                is_dir = os.path.isdir(entry)
                indicator = "/" if is_dir else ""
                result["files"].append(entry + indicator)
                count += 1

            # Add overflow indicator
            remaining = result["total"] - len(result["files"]) - len(result["filtered"])
            if remaining > 0:
                result["files"].append(f"... +{remaining} more")

        except (PermissionError, OSError) as e:
            result["files"] = [f"[error: {type(e).__name__}]"]

        return result

    def _capture_clipboard(self) -> dict:
        """Capture clipboard content via pbpaste."""
        result = {"content": None, "has_content": False, "filtered": []}

        # Check if pbpaste is available (macOS)
        if not shutil.which("pbpaste"):
            return result

        try:
            # Read clipboard
            content = _run_command(["pbpaste"], timeout=1.0)
            if content:
                result["has_content"] = True

                # Truncate if too long
                if len(content) > self.config.clipboard_max_chars:
                    content = (
                        content[: self.config.clipboard_max_chars]
                        + f"... [truncated {len(content) - self.config.clipboard_max_chars} chars]"
                    )

                # Check for sensitive content patterns
                sensitive_patterns = [
                    r"password\s*[:=]\s*\S+",
                    r"api[_-]?key\s*[:=]\s*\S+",
                    r"secret\s*[:=]\s*\S+",
                    r"token\s*[:=]\s*\S+",
                    r"-----BEGIN\s+(RSA\s+)?PRIVATE\s+KEY-----",
                    r"-----BEGIN\s+CERTIFICATE-----",
                ]

                for pattern in sensitive_patterns:
                    if re.search(pattern, content, re.IGNORECASE):
                        result["filtered"].append("clipboard (sensitive content detected)")
                        result["content"] = "[clipboard contains sensitive data - filtered]"
                        return result

                result["content"] = content

        except Exception:
            pass

        return result

    def _store_state(self, state: CapturedState):
        """Store captured state in history."""
        import sqlite3

        try:
            with _lock:
                with sqlite3.connect(str(_DB_PATH)) as c:
                    c.execute(
                        """
                        INSERT INTO state_history
                        (timestamp, pwd, git_branch, git_status, ls_summary, clipboard, metadata)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                        (
                            state.timestamp,
                            state.pwd,
                            state.git_branch,
                            state.git_status,
                            json.dumps(state.ls_files),
                            state.clipboard_content,
                            json.dumps(state.privacy_filtered),
                        ),
                    )
                    c.commit()
        except Exception:
            pass  # Non-critical failure

    def get_history(self, limit: int = 10) -> list[CapturedState]:
        """Get recent state history."""
        import sqlite3

        states = []
        try:
            with sqlite3.connect(str(_DB_PATH)) as c:
                rows = c.execute(
                    """
                    SELECT timestamp, pwd, git_branch, git_status, ls_summary, clipboard, metadata
                    FROM state_history ORDER BY timestamp DESC LIMIT ?
                """,
                    (limit,),
                ).fetchall()

                for row in rows:
                    state = CapturedState(
                        timestamp=row[0],
                        pwd=row[1],
                        git_branch=row[2],
                        git_status=row[3],
                        ls_files=json.loads(row[4]) if row[4] else [],
                        clipboard_content=row[5],
                        privacy_filtered=json.loads(row[6]) if row[6] else [],
                    )
                    states.append(state)
        except Exception:
            pass

        return states


# =============================================================================
# GhostHeader Class
# =============================================================================


class GhostHeader:
    """
    Formats captured state as invisible system header for prompt injection.

    Produces both compact (single line) and expanded (multi-line) formats.
    Designed to be stripped by the AI before response generation.
    """

    # Format templates
    COMPACT_TEMPLATE = (
        "[SYSTEM STATE: {pwd} | branch: {branch} | {git_status}{modified}{clipboard}]"
    )
    EXPANDED_TEMPLATE = """```system-context
# Ghost in the Machine — Pre-Query State Capture
pwd: {pwd}
branch: {branch}
git status: {git_status}
modified: {modified}
untracked: {untracked}
clipboard: {clipboard}
```"""

    def __init__(self, injector: StateInjector | None = None):
        self.injector = injector or StateInjector()

    def build(
        self, state: CapturedState | None = None, expanded: bool = False
    ) -> GhostHeaderData:
        """
        Build ghost header from captured state.

        Args:
            state: Pre-captured state, or None to capture fresh
            expanded: Use expanded multi-line format

        Returns:
            GhostHeaderData with formatted headers
        """
        if state is None:
            state = self.injector.capture()

        data = GhostHeaderData()
        data.components = {
            "pwd": state.pwd or "[unknown]",
            "branch": state.git_branch or "[no git]",
            "git_status": state.git_status or "unknown",
            "modified": (
                ", ".join(state.git_modified_files[:5]) if state.git_modified_files else "none"
            ),
            "modified_count": str(len(state.git_modified_files)),
            "untracked": (
                ", ".join(state.git_untracked_files[:3]) if state.git_untracked_files else "none"
            ),
            "clipboard": (
                state.clipboard_content[:100] + "..."
                if state.clipboard_content and len(state.clipboard_content) > 100
                else (state.clipboard_content or "[empty]")
            ),
        }

        # Build compact format
        modified_str = ""
        if state.git_modified_files:
            file_list = ", ".join(state.git_modified_files[:3])
            if len(state.git_modified_files) > 3:
                file_list += f" +{len(state.git_modified_files) - 3}"
            modified_str = f"modified: {file_list} | "

        clipboard_str = ""
        if state.clipboard_content and state.clipboard_content not in [
            "[clipboard contains sensitive data - filtered]",
            "[empty]",
        ]:
            clip_preview = (
                state.clipboard_content[:30] + "..."
                if len(state.clipboard_content) > 30
                else state.clipboard_content
            )
            clipboard_str = f" clipboard: {clip_preview}"

        data.compact = self.COMPACT_TEMPLATE.format(
            pwd=data.components["pwd"],
            branch=data.components["branch"],
            git_status=data.components["git_status"],
            modified=modified_str,
            clipboard=clipboard_str,
        )

        # Build expanded format
        data.expanded = self.EXPANDED_TEMPLATE.format(
            pwd=data.components["pwd"],
            branch=data.components["branch"],
            git_status=data.components["git_status"],
            modified=data.components["modified"],
            untracked=data.components["untracked"],
            clipboard=data.components["clipboard"],
        )

        return data

    def inject_into_prompt(self, prompt: str, expanded: bool = False) -> str:
        """
        Inject ghost header into a prompt.

        Args:
            prompt: Original user prompt
            expanded: Use expanded format

        Returns:
            Prompt with ghost header prepended (invisible marker)
        """
        state = self.injector.capture()
        header = self.build(state, expanded=expanded)
        header_text = header.expanded if expanded else header.compact

        # Use invisible marker that AI can parse but won't affect display
        return f"{header_text}\n\n{prompt}"

    def get_stripped_prompt(self, text: str) -> str:
        """
        Remove ghost header from text (for AI responses).

        Args:
            text: Text that may contain ghost header

        Returns:
            Text with ghost header removed
        """
        # Remove compact format
        text = re.sub(
            r"\[SYSTEM STATE:[^\]]*\]\s*",
            "",
            text,
        )

        # Remove expanded format
        text = re.sub(
            r"```system-context.*?```\s*",
            "",
            text,
            flags=re.DOTALL,
        )

        return text.strip()


# =============================================================================
# Privacy Manager
# =============================================================================


class PrivacyManager:
    """Manages privacy controls for state capture."""

    def __init__(self):
        self._load_settings()

    def _load_settings(self):
        """Load privacy settings from database."""
        import sqlite3

        self._settings: dict[str, bool] = {}
        try:
            with sqlite3.connect(str(_DB_PATH)) as c:
                rows = c.execute("SELECT key, value FROM privacy_settings").fetchall()
                self._settings = {r[0]: r[1] == "true" for r in rows}
        except Exception:
            pass

    def _save_setting(self, key: str, value: bool):
        """Save a privacy setting."""
        import sqlite3

        try:
            with _lock:
                with sqlite3.connect(str(_DB_PATH)) as c:
                    c.execute(
                        """
                        INSERT OR REPLACE INTO privacy_settings (key, value, updated_at)
                        VALUES (?, ?, ?)
                    """,
                        (key, "true" if value else "false", datetime.now().isoformat()),
                    )
                    c.commit()
            self._settings[key] = value
        except Exception:
            pass

    @property
    def clipboard_enabled(self) -> bool:
        """Check if clipboard capture is enabled."""
        return self._settings.get("clipboard_enabled", True)

    @clipboard_enabled.setter
    def clipboard_enabled(self, value: bool):
        """Enable or disable clipboard capture entirely."""
        self._save_setting("clipboard_enabled", value)

    @property
    def git_enabled(self) -> bool:
        """Check if git status capture is enabled."""
        return self._settings.get("git_enabled", True)

    @git_enabled.setter
    def git_enabled(self, value: bool):
        """Enable or disable git status capture."""
        self._save_setting("git_enabled", value)

    def add_exclusion(self, rule_type: str, pattern: str) -> bool:
        """
        Add an exclusion rule.

        Args:
            rule_type: 'path' | 'pattern' | 'env_var'
            pattern: The pattern to exclude

        Returns:
            True if successful
        """
        import sqlite3

        try:
            with _lock:
                with sqlite3.connect(str(_DB_PATH)) as c:
                    c.execute(
                        """
                        INSERT INTO exclusion_rules (rule_type, pattern, created_at)
                        VALUES (?, ?, ?)
                    """,
                        (rule_type, pattern, datetime.now().isoformat()),
                    )
                    c.commit()
            return True
        except Exception:
            return False

    def remove_exclusion(self, rule_id: int) -> bool:
        """Remove an exclusion rule by ID."""
        import sqlite3

        try:
            with _lock:
                with sqlite3.connect(str(_DB_PATH)) as c:
                    c.execute(
                        "UPDATE exclusion_rules SET is_active = 0 WHERE id = ?",
                        (rule_id,),
                    )
                    c.commit()
            return True
        except Exception:
            return False

    def get_exclusions(self) -> list[dict]:
        """Get all active exclusion rules."""
        import sqlite3

        rules = []
        try:
            with sqlite3.connect(str(_DB_PATH)) as c:
                rows = c.execute(
                    "SELECT id, rule_type, pattern, created_at FROM exclusion_rules WHERE is_active = 1"
                ).fetchall()
                rules = [
                    {
                        "id": r[0],
                        "type": r[1],
                        "pattern": r[2],
                        "created_at": r[3],
                    }
                    for r in rows
                ]
        except Exception:
            pass
        return rules


# =============================================================================
# Pre-Input Hook
# =============================================================================

# Global instances
_privacy_manager = PrivacyManager()
_default_injector: StateInjector | None = None
_default_header: GhostHeader | None = None


def _get_defaults():
    """Get or create default instances."""
    global _default_injector, _default_header

    if _default_injector is None:
        _default_injector = StateInjector()
    if _default_header is None:
        _default_header = GhostHeader(_default_injector)

    return _default_injector, _default_header


def pre_input_hook(
    config: CaptureConfig | None = None,
    expanded: bool = False,
) -> dict:
    """
    Integration hook that runs BEFORE each prompt.

    This is the main entry point for the Ghost in the Machine.
    Call this before sending user input to the AI.

    Args:
        config: Optional capture configuration
        expanded: Return expanded format details

    Returns:
        Dict with:
        - state: CapturedState object
        - header: GhostHeaderData with formatted headers
        - ghost_text: Compact header string for injection
        - expanded_text: Expanded header string for injection
        - privacy: PrivacyManager for access to controls
    """
    injector, header = _get_defaults()

    # Update config if provided
    if config is not None:
        injector.config = config

    # Respect privacy settings
    if not _privacy_manager.clipboard_enabled:
        injector.config.capture_clipboard = False
    if not _privacy_manager.git_enabled:
        injector.config.capture_git = False

    # Capture state
    state = injector.capture()
    header_data = header.build(state, expanded=expanded)

    return {
        "state": state,
        "header": header_data,
        "ghost_text": header_data.compact,
        "expanded_text": header_data.expanded,
        "privacy": _privacy_manager,
        "timestamp": state.timestamp,
        "capture_duration_ms": state.capture_duration_ms,
    }


def create_ghost_hook(
    config: CaptureConfig | None = None,
) -> Callable[[str], str]:
    """
    Create a pre-input hook function for integration.

    Args:
        config: Optional capture configuration

    Returns:
        Callable that takes a prompt and returns it with ghost header injected
    """

    def hook(prompt: str) -> str:
        result = pre_input_hook(config=config)
        return result["ghost_text"] + "\n\n" + prompt

    return hook


def strip_ghost_headers(text: str) -> str:
    """
    Remove all ghost headers from text.

    Use this on AI responses to clean them up.

    Args:
        text: Text potentially containing ghost headers

    Returns:
        Cleaned text
    """
    _, header = _get_defaults()
    return header.get_stripped_prompt(text)


# =============================================================================
# Configuration Singleton
# =============================================================================


class GhostConfig:
    """
    Global configuration singleton for Ghost in the Machine.

    Usage:
        GhostConfig.set(clipboard_enabled=False)
        GhostConfig.add_exclusion("path", "/Users/jacobbrizinski/secrets")
    """

    _instance: Optional["GhostConfig"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._privacy = _privacy_manager
        return cls._instance

    @property
    def privacy(self) -> PrivacyManager:
        """Access privacy controls."""
        return self._privacy

    def set(self, **kwargs):
        """Set configuration options via keyword arguments."""
        for key, value in kwargs.items():
            if hasattr(self._privacy, key):
                setattr(self._privacy, key, value)

    def add_exclusion(self, rule_type: str, pattern: str) -> bool:
        """Add an exclusion rule."""
        return self._privacy.add_exclusion(rule_type, pattern)

    def remove_exclusion(self, rule_id: int) -> bool:
        """Remove an exclusion rule."""
        return self._privacy.remove_exclusion(rule_id)

    def get_exclusions(self) -> list[dict]:
        """Get all exclusion rules."""
        return self._privacy.get_exclusions()


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Core classes
    "StateInjector",
    "GhostHeader",
    "PrivacyManager",
    "GhostConfig",
    # Data classes
    "CaptureConfig",
    "CapturedState",
    "GhostHeaderData",
    # Functions
    "pre_input_hook",
    "create_ghost_hook",
    "strip_ghost_headers",
]
