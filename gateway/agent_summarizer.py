"""Agent Summarizer — background summarization for autonomous agents.

Periodically creates concise summaries of agent progress for monitoring and
context management purposes.
"""

import asyncio
import logging
from typing import Optional, Dict, Callable

logger = logging.getLogger("kitty.agent_summarizer")


class AgentSummarizer:
    """Handles periodic summarization of agent work."""

    def __init__(
        self,
        session_id: int,
        get_agent_history: Callable[[], list[dict]],
        update_summary: Callable[[str], None],
        interval_seconds: int = 30,
    ):
        """
        Initialize the agent summarizer.

        Args:
            session_id: The agent session ID
            get_agent_history: Function to retrieve agent history
            update_summary: Function to update the agent summary
            interval_seconds: How often to generate summaries (default 30 seconds)
        """
        self.session_id = session_id
        self.get_agent_history = get_agent_history
        self.update_summary = update_summary
        self.interval_seconds = interval_seconds
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._last_summary: Optional[str] = None

    async def start(self):
        """Start the summarization loop."""
        if self._running:
            logger.warning(f"Summarizer already running for session {self.session_id}")
            return

        self._running = True
        self._task = asyncio.create_task(self._summarization_loop())
        logger.info(f"Started summarizer for agent session {self.session_id}")

    async def stop(self):
        """Stop the summarization loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info(f"Stopped summarizer for agent session {self.session_id}")

    async def _summarization_loop(self):
        """Main summarization loop."""
        while self._running:
            try:
                await self._generate_summary()
                await asyncio.sleep(self.interval_seconds)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(
                    f"Error in summarization loop for session {self.session_id}: {e}"
                )
                await asyncio.sleep(self.interval_seconds)  # Continue after error

    async def _generate_summary(self):
        """Generate a summary of recent agent activity."""
        try:
            history = self.get_agent_history()
            if not history or len(history) < 2:
                # Not enough history to summarize
                return

            # Get recent assistant messages (last few iterations)
            recent_messages = [
                h
                for h in history[-10:]  # Last 10 entries
                if h.get("role") == "assistant" and h.get("content")
            ]

            if not recent_messages:
                return

            # For now, we'll create a simple extractive summary
            # In a full implementation, this would call an LLM to generate the summary
            summary = self._create_extractive_summary(recent_messages)

            # Only update if summary is different enough
            if summary != self._last_summary:
                self.update_summary(summary)
                self._last_summary = summary
                logger.debug(
                    f"Updated summary for session {self.session_id}: {summary[:100]}..."
                )

        except Exception as e:
            logger.error(
                f"Failed to generate summary for session {self.session_id}: {e}"
            )

    def _create_extractive_summary(self, messages: list[dict]) -> str:
        """Create a simple extractive summary from agent messages."""
        if not messages:
            return "No activity yet"

        # Get the most recent meaningful content
        latest_msg = messages[-1]
        content = latest_msg.get("content", "").strip()

        # Try to extract key phrases or first sentence
        lines = content.split("\n")
        meaningful_lines = [
            line.strip()
            for line in lines
            if line.strip() and not line.strip().startswith("#")
        ]

        if not meaningful_lines:
            return "Agent is working..."

        # Take first meaningful line or first sentence
        first_line = meaningful_lines[0]
        if len(first_line) > 100:
            # Truncate and add ellipsis
            first_line = first_line[:97] + "..."

        # Add iteration info if available
        iteration_info = ""
        if len(messages) > 1:
            iteration_info = f" (iteration {len(messages)})"

        return f"{first_line}{iteration_info}"


# Global registry of active summarizers
_active_summarizers: Dict[int, AgentSummarizer] = {}


def start_agent_summarizer(
    session_id: int,
    get_agent_history: Callable[[], list[dict]],
    update_summary: Callable[[str], None],
    interval_seconds: int = 30,
) -> AgentSummarizer:
    """Start a summarizer for an agent session."""
    if session_id in _active_summarizers:
        logger.warning(f"Summarizer already exists for session {session_id}, replacing")
        stop_agent_summarizer(session_id)

    summarizer = AgentSummarizer(
        session_id=session_id,
        get_agent_history=get_agent_history,
        update_summary=update_summary,
        interval_seconds=interval_seconds,
    )

    _active_summarizers[session_id] = summarizer
    # Start the summarizer (fire and forget)
    asyncio.create_task(summarizer.start())

    return summarizer


def stop_agent_summarizer(session_id: int):
    """Stop the summarizer for an agent session."""
    if session_id in _active_summarizers:
        summarizer = _active_summarizers[session_id]
        # Stop the summarizer (fire and forget)
        asyncio.create_task(summarizer.stop())
        del _active_summarizers[session_id]


def get_active_summarizer_count() -> int:
    """Get the number of active summarizers."""
    return len(_active_summarizers)
