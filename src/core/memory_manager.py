"""
Centralized memory management for the supervisor system.
"""

import gc
import logging

from src.utils.token_manager import TokenManager

logger = logging.getLogger(__name__)

# Optional psutil import for system memory monitoring
try:
    import psutil

    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False
    # Don't print warning here - will be handled in initialization


class MemoryManager:
    def __init__(self, supervisor_instance=None):
        self.supervisor = supervisor_instance
        self.token_manager = TokenManager()
        try:
            import os
            import sys

            # Add the parent directory to the path to find error_tracker
            parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            if parent_dir not in sys.path:
                sys.path.insert(0, parent_dir)
            from error_tracker import ErrorTracker

            self.error_tracker = ErrorTracker()
        except ImportError as e:
            self.error_tracker = None
            # Only print warning if we're in debug mode
            if os.getenv("DEBUG"):
                logger.warning(f"Error tracker not available: {e}")
        self.memory_threshold = 80  # Trigger cleanup at 80% memory usage
        self.has_psutil = HAS_PSUTIL

    def check_memory_pressure(self) -> bool:
        """Check if system is under memory pressure."""
        if not HAS_PSUTIL:
            return False
        try:
            memory_percent = psutil.virtual_memory().percent
            return memory_percent > self.memory_threshold
        except Exception:
            return False

    def proactive_cleanup(self):
        """Perform proactive memory cleanup."""
        if self.supervisor:
            # Clean up conversation history
            if hasattr(self.supervisor, "session_history"):
                self.supervisor.session_history = self.token_manager.aggressive_compact(
                    self.supervisor.session_history
                )

            # Clean up memory cache
            if hasattr(self.supervisor, "memory"):
                self._cleanup_supervisor_memory()

        # Clean up error tracker if available
        if self.error_tracker:
            self.error_tracker.force_cleanup()

        # Force garbage collection
        gc.collect()

    def _cleanup_supervisor_memory(self):
        """Clean up supervisor's memory cache."""
        if hasattr(self.supervisor.memory, "data"):
            # Keep only recent and important facts
            data = self.supervisor.memory.data
            if len(data) > 50:
                # Sort by importance (you could add scoring logic here)
                important_keys = list(data.keys())[-25:]  # Keep last 25
                new_data = {k: data[k] for k in important_keys}
                self.supervisor.memory.data = new_data
                self.supervisor.memory._save()

    def emergency_cleanup(self):
        """Emergency memory cleanup when system is critically low."""
        if self.supervisor:
            # Aggressive history cleanup
            if hasattr(self.supervisor, "session_history"):
                # Keep only last 3 messages
                self.supervisor.session_history = self.supervisor.session_history[-3:]

            # Clear most memory cache
            if hasattr(self.supervisor, "memory"):
                self.supervisor.memory.data = {}
                self.supervisor.memory._save()

        # Clear all resolved errors if error tracker available
        if self.error_tracker:
            self.error_tracker.errors = [
                e for e in self.error_tracker.errors if not e.get("resolved", False)
            ]
            self.error_tracker._save_errors()

        # Multiple garbage collection passes
        for _ in range(3):
            gc.collect()

    def get_memory_stats(self) -> dict:
        """Get current memory usage statistics."""
        stats = {}

        if HAS_PSUTIL:
            try:
                memory = psutil.virtual_memory()
                stats["system_memory_percent"] = memory.percent
                stats["system_memory_available"] = memory.available // (1024 * 1024)  # MB
            except Exception:
                stats["system_memory_percent"] = 0
                stats["system_memory_available"] = 0
        else:
            stats["system_memory_percent"] = 0
            stats["system_memory_available"] = 0

        if self.supervisor:
            stats["session_history_size"] = len(getattr(self.supervisor, "session_history", []))
            stats["memory_cache_size"] = (
                len(getattr(self.supervisor.memory, "data", {}))
                if hasattr(self.supervisor, "memory")
                else 0
            )

        if self.error_tracker:
            stats["error_count"] = len(self.error_tracker.errors)
            stats["unresolved_errors"] = len(self.error_tracker.get_unresolved_errors())
        else:
            stats["error_count"] = 0
            stats["unresolved_errors"] = 0

        return stats

    def should_cleanup(self) -> bool:
        """Determine if cleanup is needed based on various factors."""
        stats = self.get_memory_stats()

        # Cleanup if memory usage is high
        if stats.get("system_memory_percent", 0) > self.memory_threshold:
            return True

        # Cleanup if too many messages in history
        if stats.get("session_history_size", 0) > 20:
            return True

        # Cleanup if too many unresolved errors
        if stats.get("unresolved_errors", 0) > 10:
            return True

        return False

    def auto_manage(self):
        """Automatically manage memory based on current conditions."""
        if self.check_memory_pressure():
            if HAS_PSUTIL and psutil.virtual_memory().percent > 90:
                self.emergency_cleanup()
            else:
                self.proactive_cleanup()
        elif self.should_cleanup():
            self.proactive_cleanup()
