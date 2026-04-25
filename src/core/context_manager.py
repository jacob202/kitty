"""
Unified Context Manager for Space Kitty.
Aggregates data from Honcho (psychology), CorrectionMemory (corrections/snapshots),
Journal (patterns), and RAG systems into a coherent prompt preamble.
"""

import logging
from typing import Any

from src.core.context_budget import ContextBudget, ContextSlot
from src.core.memory_surface import surface_memory
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

    def build_unified_context(
        self,
        query: str,
        domain: str,
        recent_history: list[dict[str, str]] | None = None,
        reasoning_conclusion: str | None = None,
        wiki_context: str | None = None,
    ) -> str:
        """
        Build a comprehensive context preamble for the LLM.

        Args:
            query: The current user query
            domain: The resolved domain for this query
            recent_history: Optional list of recent messages
            reasoning_conclusion: Optional conclusion from reasoning layer
            wiki_context: Optional context from wiki retrieval

        Returns:
            A formatted string to be prepended to the system prompt.
        """
        # Don't inject context for ultra-short queries (hi, fix, ok) to avoid hallucinations
        if len(query) < 15:
            return ""

        # Assemble through typed budget
        budget = ContextBudget(preset="balanced")
        has_content = False

        # 1. Psychological Approach (Honcho) → IDENTITY slot
        approach = self.honcho.get_approach_recommendation()
        if approach:
            budget.add(ContextSlot.IDENTITY, f"## Communication Strategy (Honcho):\n{approach}")
            has_content = True

        # 2. High-weight corrections (Direct feedback from Jacob) → CORRECTIONS slot
        corrections = self.correction_memory.get_relevant_context_text(query, max_items=3)
        if corrections:
            budget.add(ContextSlot.CORRECTIONS, "## Direct User Corrections (High Priority):\n" + corrections)
            has_content = True

        # 3. Project-level facts (MCP memory + Wiki) → PROJECT slot
        project_text = ""
        mcp_facts = surface_memory(query)
        if mcp_facts:
            project_text += f"### MCP Memory:\n{mcp_facts}\n"
        
        if wiki_context:
            project_text += f"### Wiki Context:\n{wiki_context}\n"

        if project_text:
            budget.add(ContextSlot.PROJECT, "## Project Knowledge:\n" + project_text.strip())
            has_content = True

        # 4. Recent context snapshots (Emotional state, topics, loops + Reasoning) → RECENT slot
        recent_text = ""
        
        if reasoning_conclusion:
            recent_text += f"### Internal Reasoning Trace:\n{reasoning_conclusion}\n"

        snapshots = self.correction_memory.get_recent_snapshots(days=7, limit=3)
        if snapshots:
            snap_part = "### Recent Context & Emotional Shifts:\n"
            for snap in snapshots:
                sentiment_word = snap.get('sentiment_label', 'neutral')
                topics = snap.get('topics', [])
                topics_str = ", ".join(topics[:3]) if topics else "general state"
                snap_part += f"- {sentiment_word} about {topics_str}. "

                open_loops = snap.get('open_loops', [])
                if open_loops:
                    snap_part += f"Open loops: {', '.join(open_loops)}. "

                if snap.get('identity_signals'):
                    snap_part += "Identity shift noted. "
                snap_part += "\n"
            recent_text += snap_part

        # 3b. Resumed conversation history → RECENT slot (if available)
        if recent_history:
            last_msgs = recent_history[-5:]  # Last 5 messages
            history_text = "### Recent Conversation (resumed session):\n"
            for msg in last_msgs:
                role = msg.get("role", "unknown")
                content = msg.get("content", "")[:200]  # Truncate each message
                history_text += f"- {role}: {content}\n"
            recent_text += history_text

        if recent_text:
            budget.add(ContextSlot.RECENT, recent_text.strip())
            has_content = True

        # 5. Behavioral Patterns (Journal) → EPHEMERAL slot
        patterns = self.journal.detect_patterns()
        if patterns:
            budget.add(ContextSlot.EPHEMERAL, "## Detected Behavioral Patterns:\n" + ", ".join(patterns))
            has_content = True

        if not has_content:
            return ""

        assembled = budget.assemble()
        if not assembled:
            return ""
        return assembled + "\n\nUse this awareness to inform tone and recall relevant details. Prioritize user corrections over all other data.\n"

    def get_current_state_summary(self) -> dict[str, Any]:
        """Get a summary of the current system state for UI/Diagnostics."""
        return {
            "psychology": self.honcho.get_current_state(),
            "approach": self.honcho.get_approach_recommendation(),
            "patterns": self.journal.detect_patterns(),
            "correction_stats": self.correction_memory.get_correction_stats(),
        }
