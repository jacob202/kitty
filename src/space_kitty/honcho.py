"""
Honcho — Psychological modeling for Space Kitty.
SQLite-backed, tracks mood/energy/patterns over time.
After every conversation, dialectic reasoning extracts signals:
  What does this reveal about Jacob?
  What patterns are emerging?
  What is he not saying?
"""

import json
import sqlite3
import threading
from datetime import datetime, timedelta

from src.core.db_config import get_db_path

_DB_PATH = get_db_path("honcho")
_lock = threading.Lock()


def _init_db():
    _DB_PATH.parent.mkdir(exist_ok=True)
    with sqlite3.connect(str(_DB_PATH)) as c:
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA synchronous=NORMAL")
        c.execute("PRAGMA cache_size=-8192")  # 8MB cache
        c.execute("""
            CREATE TABLE IF NOT EXISTS observations (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp   TEXT NOT NULL,
                category    TEXT NOT NULL,
                signal      TEXT NOT NULL,
                intensity   REAL DEFAULT 0.5,
                context     TEXT DEFAULT '{}'
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS model_state (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        # Indexes for fast lookups
        c.execute("CREATE INDEX IF NOT EXISTS idx_obs_timestamp ON observations(timestamp)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_obs_category ON observations(category)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_obs_ts_cat ON observations(timestamp, category)")
        c.commit()


_init_db()


class Honcho:
    """
    Psychological modeling engine.
    Observes conversation, extracts signals, builds a model of
    the user's current state and patterns over time.
    """

    CATEGORIES = [
        "mood",
        "energy",
        "avoidance",
        "engagement",
        "recovery",
        "grief",
        "execution",
        "research_loop",
        "planning_loop",
        "counter_dependence",
        "alibi",
    ]

    def __init__(self):
        self._conn = None

    def _get_conn(self):
        if self._conn is None:
            self._conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
            self._conn.execute("PRAGMA journal_mode=WAL")
        return self._conn

    def observe(self, category: str, signal: str, intensity: float = 0.5, context: dict = None):
        """Record a psychological observation."""
        now = datetime.now().isoformat()
        with _lock:
            conn = self._get_conn()
            conn.execute(
                "INSERT INTO observations (timestamp, category, signal, intensity, context) "
                "VALUES (?, ?, ?, ?, ?)",
                (now, category, signal, min(1.0, max(0.0, intensity)), json.dumps(context or {})),
            )
            conn.commit()

    def analyze_conversation(self, messages: list[dict[str, str]]):
        """
        Extract psychological signals from a conversation.
        This runs after every exchange — the invisible logging.
        """
        if not messages:
            return

        user_msgs = [m["content"] for m in messages if m.get("role") == "user"]
        if not user_msgs:
            return

        recent_text = " ".join(user_msgs[-5:]).lower()

        # Mood signals
        frustration_words = ["fuck", "shit", "hate", "god", "omfg", "wtf", "ugh", "frustrated"]
        frustration = sum(1 for w in frustration_words if w in recent_text)
        if frustration > 0:
            self.observe("mood", "frustrated", min(1.0, frustration * 0.25), {"trigger": "language"})

        calm_words = ["thanks", "nice", "good", "perfect", "great", "appreciate"]
        calm = sum(1 for w in calm_words if w in recent_text)
        if calm > 0:
            self.observe("mood", "calm", min(1.0, calm * 0.3), {"trigger": "language"})

        # Energy signals
        short_msgs = [m for m in user_msgs[-5:] if len(m) < 30]
        if len(short_msgs) >= 3:
            self.observe("energy", "low", 0.7, {"short_messages": len(short_msgs)})

        long_msgs = [m for m in user_msgs[-5:] if len(m) > 200]
        if long_msgs:
            self.observe("energy", "high", 0.6, {"long_messages": len(long_msgs)})

        # Avoidance signals
        topic_switches = 0
        for i in range(1, len(user_msgs[-5:])):
            prev_words = set(user_msgs[-5:][i - 1].lower().split())
            curr_words = set(user_msgs[-5:][i].lower().split())
            overlap = len(prev_words & curr_words)
            if overlap < 2:
                topic_switches += 1
        if topic_switches >= 2:
            self.observe("avoidance", "topic_switching", 0.5, {"switches": topic_switches})

        # Research loop detection
        research_words = ["research", "look into", "investigate", "explore", "what about"]
        research_count = sum(1 for msg in user_msgs[-10:] if any(w in msg.lower() for w in research_words))
        action_words = ["build", "implement", "write", "fix", "deploy", "do it", "start"]
        action_count = sum(1 for msg in user_msgs[-10:] if any(w in msg.lower() for w in action_words))
        if research_count > 3 and action_count == 0:
            self.observe("research_loop", "active", 0.8, {"research": research_count, "action": action_count})

        # Execution gap
        plan_words = ["plan", "strategy", "design", "architecture", "roadmap"]
        plan_count = sum(1 for msg in user_msgs[-10:] if any(w in msg.lower() for w in plan_words))
        if plan_count > 3 and action_count == 0:
            self.observe("planning_loop", "active", 0.7, {"planning": plan_count, "action": action_count})

        # Counter-dependence detection: runs on opposition, not encouragement
        # Signal: responds to challenge but ignores encouragement
        challenge_words = ["but", "however", "actually", "really though", "the thing is"]

        # Check if recent messages show opposition pattern
        recent_lower = " ".join(user_msgs[-5:]).lower()
        if any(w in recent_lower for w in challenge_words):
            # Counter-dependent: pushes back on suggestions
            pushback_count = sum(1 for w in challenge_words if w in recent_lower)
            if pushback_count >= 1:
                self.observe("counter_dependence", "active", 0.6, {"pushback": pushback_count})

        # Alibi pattern: not fully trying protects against confirming core fear
        # Signal: "I could but...", consistently unfinished tasks, capability vs output gap
        alibi_words = ["i could", "i would", "i should", "i'm going to", "i meant to", "i was going to"]
        alibi_count = sum(1 for msg in user_msgs[-10:] for w in alibi_words if w in msg.lower())
        if alibi_count >= 2:
            self.observe("alibi", "active", 0.5, {"alibi_phrases": alibi_count})

    def get_recent_observations(self, hours: int = 24, limit: int = 50) -> list[dict]:
        """Get observations from the last N hours."""
        cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
        with _lock:
            with sqlite3.connect(str(_DB_PATH)) as c:
                rows = c.execute(
                    "SELECT timestamp, category, signal, intensity, context "
                    "FROM observations WHERE timestamp > ? ORDER BY timestamp DESC LIMIT ?",
                    (cutoff, limit),
                ).fetchall()
        return [
            {
                "timestamp": r[0],
                "category": r[1],
                "signal": r[2],
                "intensity": r[3],
                "context": json.loads(r[4]),
            }
            for r in rows
        ]

    def get_current_state(self) -> dict[str, dict[str, object]]:
        """
        Get the current psychological model.
        Returns the most recent signal for each category.
        Uses a single query with GROUP BY instead of N sequential queries.
        """
        state: dict[str, dict[str, object]] = {}
        with _lock:
            conn = self._get_conn()
            rows = conn.execute(
                "SELECT category, signal, intensity FROM observations "
                "WHERE (category, timestamp) IN ("
                "  SELECT category, MAX(timestamp) FROM observations GROUP BY category"
                ")"
            ).fetchall()
        for row in rows:
            state[row[0]] = {"signal": row[1], "intensity": row[2]}
        return state

    def get_approach_recommendation(self) -> str:
        """
        Answer: "What's the best way to reach Jacob right now?"
        Based on current state, return communication guidance.
        """
        state = self.get_current_state()

        mood = state.get("mood", {})
        energy = state.get("energy", {})
        avoidance = state.get("avoidance", {})

        mood_signal = mood.get("signal", "unknown")
        energy_signal = energy.get("signal", "unknown")

        if mood_signal == "frustrated":
            return "Direct and action-oriented. No preamble. Show results, not plans. He's frustrated — prove it works."
        if energy_signal == "low":
            return "Keep it short. One thing at a time. Don't overwhelm. He's running low."
        if avoidance.get("signal") == "topic_switching":
            return "Something's being avoided. Name it gently. Don't push, but don't ignore."
        if state.get("research_loop", {}).get("signal") == "active":
            return "Research loop detected. Redirect to smallest executable step. Challenge gently."
        if state.get("planning_loop", {}).get("signal") == "active":
            return "Planning marathon. Beautiful architecture, no implementation. Name it. Redirect to action."
        if mood_signal == "calm" and energy_signal == "high":
            return "Good headspace. Challenge him. Push for execution. This is the window."
        return "Neutral state. Be present. Listen. Follow his lead."

    def update_model(self, key: str, value: str):
        """Update a persistent model state value."""
        now = datetime.now().isoformat()
        with _lock:
            with sqlite3.connect(str(_DB_PATH)) as c:
                c.execute(
                    "INSERT OR REPLACE INTO model_state (key, value, updated_at) VALUES (?, ?, ?)",
                    (key, value, now),
                )
                c.commit()

    def get_model_value(self, key: str) -> str | None:
        """Get a persistent model state value."""
        with sqlite3.connect(str(_DB_PATH)) as c:
            row = c.execute("SELECT value FROM model_state WHERE key = ?", (key,)).fetchone()
        return row[0] if row else None

    def get_opener(self) -> tuple:
        """
        Determine if we should show a morning/welcome-back opener.
        Returns: (should_show: bool, opener_text: str)

        Logic:
        - Gap > 4 hours AND time is 6am-12pm → morning opener
        - Gap > 12 hours any time → welcome back opener
        - Otherwise → no opener
        """
        import random
        from datetime import datetime

        now = datetime.now()
        current_hour = now.hour

        # Get last message time from model_state
        last_msg_time = self.get_model_value("last_message_time")

        gap_hours = 999  # default to large gap if no history

        if last_msg_time:
            try:
                last_dt = datetime.fromisoformat(last_msg_time)
                gap = now - last_dt
                gap_hours = gap.total_seconds() / 3600
            except Exception:
                gap_hours = 999  # treat invalid time as large gap

        # Update last message time to now
        self.update_model("last_message_time", now.isoformat())

        # Define openers
        morning_openers = [
            "Hey, how's the morning going?",
            "What's on your mind today?",
            "Tell me something.",
            "How was last night?",
        ]

        welcome_openers = [
            "Hey — welcome back. What's happening?",
            "It's been a while. What's going on?",
            "Hey. What's new?",
        ]

        # Determine if we should show an opener
        should_show = False
        opener = ""

        # Morning opener: gap > 4 hours AND between 6am-12pm
        if gap_hours > 4 and 6 <= current_hour < 12:
            should_show = True
            opener = random.choice(morning_openers)

        # Welcome back: gap > 12 hours any time
        elif gap_hours > 12:
            should_show = True
            opener = random.choice(welcome_openers)

        # Additional: if it's been a really long time (24+ hours), always show
        elif gap_hours > 24:
            should_show = True
            opener = random.choice(welcome_openers)

        return should_show, opener
