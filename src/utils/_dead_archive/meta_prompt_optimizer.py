"""
Meta-Prompt Optimizer - Kitty writes better Kittys.

Problem: After a week of use, you'll notice patterns:
- "Kitty always over-explains when I ask for bash"
- "She uses outdated syntax for yt-dlp"
- "User says 'tl;dr' after long responses"

Solution: Analyze conversation logs, identify friction points,
and rewrite prompts to reduce friction by 20%+.

The Optimizer Loop:
1. Scan logs for friction patterns
2. Generate improved prompt snippets
3. Present diff to user
4. Apply changes
5. Auto-rollback if satisfaction drops
"""

import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from difflib import unified_diff
from enum import Enum

from src.core.db_config import get_db_path

_DB_PATH = get_db_path("meta_optimizer")
_lock = sqlite3.connect(str(_DB_PATH), check_same_thread=False)


def _init_db():
    _DB_PATH.parent.mkdir(exist_ok=True)
    with sqlite3.connect(str(_DB_PATH)) as c:
        c.execute("PRAGMA journal_mode=WAL")

        # Prompt versions
        c.execute("""
            CREATE TABLE IF NOT EXISTS prompt_versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                component TEXT NOT NULL,
                version INTEGER NOT NULL,
                prompt_text TEXT NOT NULL,
                created_at TEXT NOT NULL,
                created_reason TEXT,
                user_approved INTEGER DEFAULT 0
            )
        """)

        # Friction events detected
        c.execute("""
            CREATE TABLE IF NOT EXISTS friction_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                friction_type TEXT NOT NULL,
                context_before TEXT,
                context_after TEXT,
                resolved INTEGER DEFAULT 0,
                resolution TEXT
            )
        """)

        # Satisfaction metrics
        c.execute("""
            CREATE TABLE IF NOT EXISTS satisfaction_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                component TEXT,
                metric_type TEXT NOT NULL,
                value REAL,
                notes TEXT
            )
        """)

        # Current active versions
        c.execute("""
            CREATE TABLE IF NOT EXISTS active_prompts (
                component TEXT PRIMARY KEY,
                version_id INTEGER,
                FOREIGN KEY (version_id) REFERENCES prompt_versions(id)
            )
        """)

        c.commit()


_init_db()


class FrictionType(Enum):
    USER_CORRECTION = "user_correction"
    TLDR_AFTER_LONG = "tldr_after_long"
    COMMAND_FAILED = "command_failed"
    STOP_WAIT = "stop_wait"
    REPEATED_QUESTION = "repeated_question"
    WRONG_DOMAIN = "wrong_domain"




@dataclass
class FrictionEvent:
    id: int
    timestamp: str
    friction_type: str
    context_before: str
    context_after: str
    resolved: bool = False


@dataclass
class PromptDelta:
    component: str
    old_text: str
    new_text: str
    reason: str
    friction_addressed: str
    confidence: float  # How confident we are this will help


class MetaPromptOptimizer:
    """
    Analyzes Kitty's behavior and rewrites prompts for continuous improvement.

    Usage:
        optimizer = MetaPromptOptimizer()
        optimizer.scan_logs(hours=168)  # Last week
        deltas = optimizer.generate_improvements()
        if deltas:
            optimizer.present_diffs(deltas)
    """

    # Friction patterns to detect
    CORRECTION_PATTERNS = [
        (r"no[,]?\s*(actually|wait|thats?)\s", "user_correction"),
        (r"(not|never|don'?t)\s+(use|try)\s", "user_correction"),
        (r"(should be|must be|needs? to be)\s", "user_correction"),
        (r"(wrong|incorrect|inaccurate)\s", "user_correction"),
    ]

    TLDR_PATTERNS = [
        r"tl;dr",
        r"too long",
        r"didn'?t read",
        r"summarize",
        r"shorten it",
        r"keep it brief",
    ]

    COMMAND_FAILURE_PATTERNS = [
        r"command\s+failed",
        r"error:",
        r"not found",
        r"permission denied",
        r"invalid option",
        r"deprecated",
    ]

    STOP_PATTERNS = [
        r"wait[,]?\s*stop",
        r"cancel",
        r"never mind",
        r"forget (that|it)",
        r"abort",
    ]

    def __init__(self):
        self._detected_friction: list[FrictionEvent] = []
        self._proposed_deltas: list[PromptDelta] = []

    def scan_logs(self, hours: int = 168) -> list[FrictionEvent]:
        """
        Scan conversation logs for friction patterns.

        Args:
            hours: How far back to scan (default 168 = 1 week)

        Returns:
            List of detected friction events
        """
        cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()

        with sqlite3.connect(str(_DB_PATH)) as c:
            rows = c.execute(
                """
                SELECT timestamp, role, content FROM conversation_logs
                WHERE timestamp > ?
                ORDER BY timestamp
            """,
                (cutoff,),
            ).fetchall()

        self._detected_friction = []

        # Analyze conversation pairs
        prev_role = None
        prev_content = None

        for timestamp, role, content in rows:
            if prev_role == "user" and role == "assistant":
                # Check for friction after assistant response
                friction = self._check_friction(prev_content, content, timestamp)
                if friction:
                    self._detected_friction.append(friction)

            prev_role = role
            prev_content = content

        return self._detected_friction

    def _check_friction(
        self, user_msg: str, kitty_response: str, timestamp: str
    ) -> FrictionEvent | None:
        """Check a conversation pair for friction patterns."""
        user_lower = user_msg.lower()
        response_len = len(kitty_response)

        # User correction
        for pattern, ftype in self.CORRECTION_PATTERNS:
            if re.search(pattern, user_lower):
                return FrictionEvent(
                    id=0,
                    timestamp=timestamp,
                    friction_type=ftype,
                    context_before=kitty_response[:200],
                    context_after=user_msg,
                )

        # Too long response followed by tl;dr
        if response_len > 500:
            for pattern in self.TLDR_PATTERNS:
                if pattern in user_lower:
                    return FrictionEvent(
                        id=0,
                        timestamp=timestamp,
                        friction_type="tldr_after_long",
                        context_before=kitty_response[:200],
                        context_after=user_msg,
                    )

        # Stop mid-execution
        for pattern in self.STOP_PATTERNS:
            if re.search(pattern, user_lower):
                return FrictionEvent(
                    id=0,
                    timestamp=timestamp,
                    friction_type="stop_wait",
                    context_before=kitty_response[:200],
                    context_after=user_msg,
                )

        return None

    def generate_improvements(self) -> list[PromptDelta]:
        """
        Generate prompt improvement suggestions based on detected friction.

        Returns:
            List of PromptDelta objects with proposed changes
        """
        self._proposed_deltas = []

        # Group friction by type
        by_type: dict[str, list[FrictionEvent]] = {}
        for f in self._detected_friction:
            by_type.setdefault(f.friction_type, []).append(f)

        # Generate deltas for each friction type
        for ftype, events in by_type.items():
            delta = self._suggest_delta(ftype, events)
            if delta:
                self._proposed_deltas.append(delta)

        return self._proposed_deltas

    def _suggest_delta(
        self, friction_type: str, events: list[FrictionEvent]
    ) -> PromptDelta | None:
        """Generate a specific prompt delta for a friction type."""

        if friction_type == "user_correction":
            # Find what was corrected
            corrections = []
            for e in events:
                # Extract what user said was wrong
                match = re.search(r"(not|never)\s+(use|try|be)\s+(\w+)", e.context_after.lower())
                if match:
                    corrections.append(match.group(3))

            if corrections:
                corrections_text = ", ".join(set(corrections))
                return PromptDelta(
                    component="general",
                    old_text="Be helpful and thorough.",
                    new_text=f"Be helpful. When suggesting {corrections_text}, use current best practices — verify syntax is not deprecated.",
                    reason="User corrections detected for these terms",
                    friction_addressed="user_correction",
                    confidence=0.8,
                )

        elif friction_type == "tldr_after_long":
            # User wants shorter responses
            return PromptDelta(
                component="general",
                old_text="Be helpful and thorough.",
                new_text="Be concise by default. Lead with the answer. Add details only if asked. Aim for 2-3 sentences unless complexity demands more.",
                reason="Multiple 'tl;dr' or 'too long' responses detected",
                friction_addressed="tldr_after_long",
                confidence=0.9,
            )

        elif friction_type == "stop_wait":
            # User interrupted execution
            return PromptDelta(
                component="general",
                old_text="Execute commands immediately.",
                new_text="Before executing destructive commands (rm, mv overwrite, etc.), confirm with the user. For other commands, briefly describe what will happen first.",
                reason="User issued stop/cancel during execution",
                friction_addressed="stop_wait",
                confidence=0.85,
            )

        elif friction_type == "command_failed":
            return PromptDelta(
                component="tool_agent",
                old_text="Use standard CLI commands.",
                new_text="Use verified, non-deprecated commands. After any command, check for 'command not found' or 'deprecated' in output. If error, try alternative or report.",
                reason="Commands failed with common errors",
                friction_addressed="command_failed",
                confidence=0.75,
            )

        return None

    def present_diffs(self, deltas: list[PromptDelta] = None) -> str:
        """
        Generate a unified diff showing proposed changes.

        Returns:
            Formatted diff string
        """
        if deltas is None:
            deltas = self._proposed_deltas

        lines = [
            "=" * 70,
            "META-PROMPT OPTIMIZER: Proposed Changes",
            "=" * 70,
            "",
            f"Detected {len(self._detected_friction)} friction events.",
            f"Generated {len(deltas)} improvement suggestions.",
            "",
        ]

        for i, delta in enumerate(deltas, 1):
            lines.extend(
                [
                    "-" * 70,
                    f"SUGGESTION #{i}: {delta.component}",
                    f"Friction addressed: {delta.friction_type}",
                    f"Confidence: {delta.confidence:.0%}",
                    f"Reason: {delta.reason}",
                    "-" * 70,
                    "--- current",
                    "+++ proposed",
                ]
            )

            # Generate diff
            diff = unified_diff(
                delta.old_text.splitlines(keepends=True),
                delta.new_text.splitlines(keepends=True),
                fromfile="current",
                tofile="proposed",
                lineterm="",
            )
            lines.extend(diff)
            lines.append("")

        lines.extend(
            [
                "=" * 70,
                "Apply these changes?",
                "  [Yes]     - Apply all suggestions",
                "  [Review]  - Apply one by one",
                "  [No]      - Discard all",
                "=" * 70,
            ]
        )

        return "\n".join(lines)

    def apply_delta(self, delta: PromptDelta) -> int:
        """
        Apply a single prompt delta to the system.

        Returns:
            New prompt version ID
        """
        now = datetime.now().isoformat()

        with sqlite3.connect(str(_DB_PATH)) as c:
            # Get next version number
            row = c.execute(
                """
                SELECT MAX(version) FROM prompt_versions WHERE component = ?
            """,
                (delta.component,),
            ).fetchone()
            next_version = (row[0] or 0) + 1

            # Insert new version
            cursor = c.execute(
                """
                INSERT INTO prompt_versions
                (component, version, prompt_text, created_at, created_reason)
                VALUES (?, ?, ?, ?, ?)
            """,
                (delta.component, next_version, delta.new_text, now, delta.reason),
            )
            version_id = cursor.lastrowid

            # Update active prompt
            c.execute(
                """
                INSERT OR REPLACE INTO active_prompts (component, version_id)
                VALUES (?, ?)
            """,
                (delta.component, version_id),
            )

            c.commit()

        return version_id

    def rollback(self, component: str, version_id: int = None) -> bool:
        """
        Rollback to a previous prompt version.

        Args:
            component: Which component to rollback
            version_id: Specific version to rollback to, or None for previous

        Returns:
            True if successful
        """
        with sqlite3.connect(str(_DB_PATH)) as c:
            if version_id is None:
                # Get previous version
                row = c.execute(
                    """
                    SELECT id FROM prompt_versions
                    WHERE component = ?
                    ORDER BY version DESC
                    LIMIT 1 OFFSET 1
                """,
                    (component,),
                ).fetchone()
                version_id = row[0] if row else None

            if version_id:
                c.execute(
                    """
                    UPDATE active_prompts SET version_id = ? WHERE component = ?
                """,
                    (version_id, component),
                )
                c.commit()
                return True
        return False

    def record_satisfaction(self, component: str, metric: float, notes: str = None):
        """Record a satisfaction metric after prompt change."""
        now = datetime.now().isoformat()

        with sqlite3.connect(str(_DB_PATH)) as c:
            c.execute(
                """
                INSERT INTO satisfaction_metrics (timestamp, component, metric_type, value, notes)
                VALUES (?, ?, ?, ?, ?)
            """,
                (now, component, "user_satisfaction", metric, notes),
            )
            c.commit()

    def check_rollback_needed(self, component: str, threshold: float = 0.7) -> bool:
        """
        Check if satisfaction dropped below threshold after recent change.

        Returns:
            True if rollback should be triggered
        """
        with sqlite3.connect(str(_DB_PATH)) as c:
            # Get satisfaction scores after last change
            row = c.execute(
                """
                SELECT AVG(value), COUNT(*) FROM satisfaction_metrics
                WHERE component = ? AND metric_type = 'user_satisfaction'
                AND timestamp > (
                    SELECT created_at FROM prompt_versions
                    WHERE component = ?
                    ORDER BY id DESC LIMIT 1
                )
            """,
                (component, component),
            ).fetchone()

            if row[0] and row[1] >= 3:  # Need at least 3 measurements
                return row[0] < threshold

        return False


# Convenience functions
def optimize_prompts(hours: int = 168) -> tuple[list[FrictionEvent], list[PromptDelta]]:
    """Run the full optimization loop."""
    optimizer = MetaPromptOptimizer()
    friction = optimizer.scan_logs(hours)
    deltas = optimizer.generate_improvements()
    return friction, deltas
