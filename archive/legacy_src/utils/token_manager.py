"""
Token management for efficient context handling.
"""

class TokenManager:
    def __init__(self, max_tokens=80000):
        self.max_tokens = max_tokens

    def estimate_tokens(self, text: str) -> int:
        """Estimate token count using a more accurate heuristic."""
        # Count words and punctuation for better estimation
        words = len(text.split())
        chars = len(text)
        # Average of word-based and char-based estimates
        return int((words * 1.3 + chars // 4) / 2)

    def compact_history(self, history: list) -> list:
        """Compact conversation history while preserving important context."""
        if len(history) < 8:
            return history

        # Keep system prompts
        sys_prompts = [h for h in history if h.get("role") == "system"]

        # Keep recent messages with priority for user queries
        recent = []
        user_count = 0
        assistant_count = 0

        # Process from most recent to oldest
        for msg in reversed(history):
            if msg.get("role") == "user":
                if user_count < 2:  # Keep last 2 user messages
                    recent.insert(0, msg)
                    user_count += 1
            elif msg.get("role") == "assistant":
                if assistant_count < 2:  # Keep last 2 assistant responses
                    recent.insert(0, msg)
                    assistant_count += 1
            elif msg.get("role") == "system":
                # System messages are handled separately
                pass

            if len(recent) >= 6:  # Total limit
                break

        # Add a summary message if we're compacting significantly
        if len(history) > 10:
            summary_msg = {
                "role": "system",
                "content": f"[Previous {len(history) - len(recent)} messages compacted for context efficiency]"
            }
            recent.insert(0, summary_msg)

        return sys_prompts + recent

    def aggressive_compact(self, history: list) -> list:
        """More aggressive compaction for memory pressure situations."""
        min_history_size = 5

        if len(history) <= min_history_size:
            return history

        # Keep first message (system), last few messages, and compress middle
        compressed = []
        if history:
            compressed.append(history[0])  # Keep system message

            # Compress middle messages into summary
            if len(history) > min_history_size + 2:
                middle_start = 1
                middle_end = len(history) - min_history_size
                middle_messages = history[middle_start:middle_end]

                # Create summary of middle conversation
                summary_content = self._summarize_messages(middle_messages)
                compressed.append({
                    "role": "assistant",
                    "content": f"[COMPRESSED HISTORY: {summary_content}]"
                })

            # Keep recent messages
            compressed.extend(history[-min_history_size:])

        return compressed

    def _summarize_messages(self, messages: list) -> str:
        """Create a brief summary of conversation messages."""
        topics = []
        for msg in messages:
            content = str(msg.get('content', ''))[:100]  # First 100 chars
            if content.strip():
                topics.append(content.strip())

        return f"Discussed: {'; '.join(topics[:3])}..." if topics else "General conversation"


    def should_compact(self, history: list, current_prompt: str) -> bool:
        """Determine if history should be compacted based on token estimates."""
        total_tokens = sum(self.estimate_tokens(msg.get("content", "")) for msg in history)
        current_tokens = self.estimate_tokens(current_prompt)
        return (total_tokens + current_tokens) > (self.max_tokens * 0.8)

    def basic_memory_cleanup(self, supervisor_instance):
        """Basic memory cleanup without external dependencies."""
        import gc

        # Simple history truncation
        if hasattr(supervisor_instance, 'session_history'):
            if len(supervisor_instance.session_history) > 15:
                supervisor_instance.session_history = supervisor_instance.session_history[-10:]

        # Simple memory cache cleanup
        if hasattr(supervisor_instance, 'memory') and hasattr(supervisor_instance.memory, 'data'):
            if len(supervisor_instance.memory.data) > 75:
                # Keep only recent facts
                recent_keys = list(supervisor_instance.memory.data.keys())[-40:]
                new_data = {k: supervisor_instance.memory.data[k] for k in recent_keys}
                supervisor_instance.memory.data = new_data
                if hasattr(supervisor_instance.memory, '_save'):
                    supervisor_instance.memory._save()

        # Force garbage collection
        gc.collect()
