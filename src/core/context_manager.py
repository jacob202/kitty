"""
Unified Context Manager for Space Kitty.
Aggregates data from Honcho (psychology), CorrectionMemory (corrections/snapshots),
Journal (patterns), and RAG systems into a coherent prompt preamble.
"""

import logging
from typing import Any

from src.memory.correction_memory import CorrectionMemory
from src.space_kitty.honcho import Honcho
from src.space_kitty.journal_interface import JournalInterface

logger = logging.getLogger(__name__)


class ContextManager:
    """
    Orchestrates context retrieval from multiple memory and psychological subsystems.
    """

    def __init__(self):
        self.honcho = Honcho()
        self.correction_memory = CorrectionMemory()
        self.journal = JournalInterface()

    def build_unified_context(self, query: str, domain: str) -> str:
        """
        Build a comprehensive context preamble for the LLM.

        Args:
            query: The current user query
            domain: The resolved domain for this query

        Returns:
            A formatted string to be prepended to the system prompt.
        """
        # Don't inject context for ultra-short queries (hi, fix, ok) to avoid hallucinations
        if len(query) < 15:
            return ""

        preamble_parts = []

        # 1. Psychological Approach (Honcho)
        approach = self.honcho.get_approach_recommendation()
        if approach:
            preamble_parts.append(f"## Communication Strategy (Honcho):\n{approach}")

        # 2. High-weight corrections (Direct feedback from Jacob)
        corrections = self.correction_memory.get_relevant_context_text(query, max_items=3)
        if corrections:
            preamble_parts.append("## Direct User Corrections (High Priority):\n" + corrections)

        # 3. Recent context snapshots (Emotional state, topics, loops)
        snapshots = self.correction_memory.get_recent_snapshots(days=7, limit=3)
        if snapshots:
            snap_text = "## Recent Context & Emotional Shifts:\n"
            for snap in snapshots:
                sentiment_word = snap.get('sentiment_label', 'neutral')
                topics = snap.get('topics', [])
                topics_str = ", ".join(topics[:3]) if topics else "general state"
                snap_text += f"- {sentiment_word} about {topics_str}. "

                open_loops = snap.get('open_loops', [])
                if open_loops:
                    snap_text += f"Open loops: {', '.join(open_loops)}. "

                if snap.get('identity_signals'):
                    snap_text += "Identity shift noted. "
                snap_text += "\n"
            preamble_parts.append(snap_text)

        # 4. Behavioral Patterns (Journal)
        patterns = self.journal.detect_patterns()
        if patterns:
            pattern_text = "## Detected Behavioral Patterns:\n"
            pattern_text += ", ".join(patterns)
            preamble_parts.append(pattern_text)

        if not preamble_parts:
            return ""

        full_preamble = "\n\n".join(preamble_parts)
        full_preamble += "\n\nUse this awareness to inform tone and recall relevant details. Prioritize user corrections over all other data.\n"

        return full_preamble

    def get_current_state_summary(self) -> dict[str, Any]:
        """Get a summary of the current system state for UI/Diagnostics."""
        return {
            "psychology": self.honcho.get_current_state(),
            "approach": self.honcho.get_approach_recommendation(),
            "patterns": self.journal.detect_patterns(),
            "correction_stats": self.correction_memory.get_correction_stats(),
        }
