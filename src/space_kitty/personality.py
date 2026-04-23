"""
Space Kitty personality system.
Loads SOUL.md (patterns + voice) and AURA.yaml (branding).
"""

import re
from pathlib import Path
from typing import Any

from src.core.aura_loader import get_branding


class KittyPersonality:
    """Load and serve personality patterns, voice, and mood detection."""

    def __init__(self):
        self.soul_path = Path("src/space_kitty/SOUL.md")
        self.branding = get_branding()
        self._load_soul()

    def _load_soul(self):
        """Load SOUL.md as full text plus extract key sections."""
        if not self.soul_path.exists():
            self.soul_text = ""
            self.core_patterns = {}
            self.voice = {}
            self.mood_signals = {}
            return

        self.soul_text = self.soul_path.read_text()
        # Extract sections by their actual names in the document
        self.core_patterns = self._parse_section(self.soul_text, "The Patterns I Watch For")
        self.voice = self._parse_section(self.soul_text, "How I Communicate")
        self.mood_signals = self._parse_section(self.soul_text, "How I Stay Present")

    def _parse_section(self, content: str, section_name: str) -> dict[str, str]:
        """Extract a markdown section into a dict."""
        pattern = rf"## {section_name}\n(.*?)(?=## |\Z)"
        match = re.search(pattern, content, re.DOTALL)
        if not match:
            return {}

        section = match.group(1)
        result = {}
        for line in section.split("\n"):
            if line.startswith("- **"):
                parts = line.split(":** ", 1)
                if len(parts) == 2:
                    key = parts[0].replace("- **", "").replace("**", "").strip()
                    value = parts[1].strip()
                    result[key] = value
        return result

    def get_system_context(self) -> str:
        """Return SOUL content suitable for injection into a system prompt."""
        if not hasattr(self, "soul_text") or not self.soul_text:
            return ""
        # Extract the identity + communication + patterns sections — skip architecture/context
        sections = ["Who I Am", "How I Communicate", "The Patterns I Watch For", "What I Don't Do"]
        parts = []
        for section in sections:
            match = re.search(rf"## {re.escape(section)}\n(.*?)(?=## |\Z)", self.soul_text, re.DOTALL)
            if match:
                parts.append(f"## {section}\n{match.group(1).strip()}")
        return "\n\n".join(parts)

    def get_voice(self) -> str:
        """Get communication voice summary."""
        if not self.voice:
            return "direct, pattern-detecting, skeptical but willing"
        return " | ".join(self.voice.values())[:200]

    def get_branding(self) -> dict[str, Any]:
        """Return AURA.yaml branding."""
        return self.branding

    def detect_mood(self, history: list[dict[str, str]]) -> str:
        """Detect mood from conversation history."""
        if not history:
            return "focused"

        # Count research vs action
        research_count = sum(
            1 for msg in history
            if "research" in msg.get("content", "").lower()
        )
        action_count = sum(
            1 for msg in history
            if any(word in msg.get("content", "").lower()
                   for word in ["implement", "write", "fix", "deploy"])
        )

        # Spinning: lots of research, no action
        if research_count > 3 and action_count == 0:
            return "spinning"

        # Exploring: mixed research and action
        if research_count > 0 and action_count > 0:
            return "exploring"

        # Drained: short replies, repetition
        recent = [m.get("content", "") for m in history[-3:]]
        if len(recent) == 3 and all(len(c) < 50 for c in recent):
            return "drained"

        return "focused"

    def get_patterns_summary(self) -> str:
        """Return core patterns as readable summary."""
        if not self.core_patterns:
            return "No patterns loaded"
        return " | ".join(
            f"{k}: {v[:50]}" for k, v in list(self.core_patterns.items())[:3]
        )
