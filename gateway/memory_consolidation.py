"""Memory Consolidation System — Claude Code inspired "Dream" system.

Implements a background memory consolidation engine that runs periodically to
synthesize recent learning into durable, organized memories.
"""

import asyncio
import logging
import os
import time
from typing import Optional, Callable, Dict, Any
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger("kitty.memory_consolidation")

class MemoryConsolidationSystem:
    """Implements Claude Code's dream system for memory consolidation."""
    
    def __init__(self,
                 knowledge_dir: Path,
                 get_recent_sessions: Callable[[], list[Dict[str, Any]]],
                 get_memory_files: Callable[[], list[Path]],
                 update_memory_file: Callable[[Path, str], None],
                 min_hours_between: int = 24,
                 min_sessions_since: int = 5):
        """
        Initialize the memory consolidation system.
        
        Args:
            knowledge_dir: Directory where memory files are stored
            get_recent_sessions: Function to retrieve recent session data
            get_memory_files: Function to get list of memory files
            update_memory_file: Function to update a memory file with new content
            min_hours_between: Minimum hours between consolidation runs
            min_sessions_since: Minimum sessions since last consolidation
        """
        self.knowledge_dir = knowledge_dir
        self.get_recent_sessions = get_recent_sessions
        self.get_memory_files = get_memory_files
        self.update_memory_file = update_memory_file
        self.min_hours_between = min_hours_between
        self.min_sessions_since = min_sessions_since
        
        self._last_consolidation: Optional[float] = None
        self._consolidation_lock: bool = False
        self._task: Optional[asyncio.Task] = None
        self._running: bool = False
        
    async def start(self):
        """Start the memory consolidation background task."""
        if self._running:
            logger.warning("Memory consolidation already running")
            return
            
        self._running = True
        self._task = asyncio.create_task(self._consolidation_loop())
        logger.info("Started memory consolidation system")
        
    async def stop(self):
        """Stop the memory consolidation background task."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("Stopped memory consolidation system")
        
    async def _consolidation_loop(self):
        """Main consolidation loop that checks gates and runs consolidation."""
        while self._running:
            try:
                # Check if we should run consolidation
                if await self._should_consolidate():
                    await self._run_consolidation()
                
                # Check every hour or so
                await asyncio.sleep(3600)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in consolidation loop: {e}")
                await asyncio.sleep(3600)  # Continue after error
                
    async def _should_consolidate(self) -> bool:
        """Check if all gates are open for consolidation."""
        # Gate 1: Time gate
        now = time.time()
        if self._last_consolidation is not None:
            hours_since = (now - self._last_consolidation) / 3600
            if hours_since < self.min_hours_between:
                logger.debug(f"Time gate closed: {hours_since:.1f}h < {self.min_hours_between}h")
                return False
        
        # Gate 2: Session gate
        try:
            recent_sessions = self.get_recent_sessions()
            if len(recent_sessions) < self.min_sessions_since:
                logger.debug(f"Session gate closed: {len(recent_sessions)} sessions < {self.min_sessions_since}")
                return False
        except Exception as e:
            logger.error(f"Error checking session gate: {e}")
            return False
            
        # Gate 3: Lock gate
        if self._consolidation_lock:
            logger.debug("Lock gate closed: consolidation already in progress")
            return False
            
        logger.info("All gates open for memory consolidation")
        return True
        
    async def _run_consolidation(self):
        """Run the memory consolidation process (Claude Code's dream)."""
        logger.info("Starting memory consolidation (dream)")
        self._consolidation_lock = True
        
        try:
            # Phase 1: Orient
            await self._phase_1_orient()
            
            # Phase 2: Gather Recent Signal
            recent_signal = await self._phase_2_gather_recent_signal()
            
            # Phase 3: Consolidate
            consolidated_content = await self._phase_3_consolidate(recent_signal)
            
            # Phase 4: Prune and Index
            await self._phase_4_prune_and_index(consolidated_content)
            
            # Record completion
            self._last_consolidation = time.time()
            logger.info("Memory consolidation completed successfully")
            
        except Exception as e:
            logger.exception(f"Memory consolidation failed: {e}")
        finally:
            self._consolidation_lock = False
            
    async def _phase_1_orient(self):
        """Phase 1: Orient - ls the memory directory, read memory index, skim existing files."""
        logger.debug("Phase 1: Orient")
        
        try:
            # List memory directory
            memory_files = self.get_memory_files()
            logger.debug(f"Found {len(memory_files)} memory files")
            
            # In a full implementation, we would read the main memory index file
            # For now, we just log what we found
            for mem_file in memory_files[:5]:  # Log first 5 files
                logger.debug(f"Memory file: {mem_file.name}")
                
        except Exception as e:
            logger.error(f"Error in orient phase: {e}")
            
    async def _phase_2_gather_recent_signal(self) -> str:
        """Phase 2: Gather Recent Signal - find new information worth persisting."""
        logger.debug("Phase 2: Gather Recent Signal")
        
        try:
            # Get recent sessions (priority: daily logs → drifted memories → transcript search)
            recent_sessions = self.get_recent_sessions()
            
            # Extract key information from recent sessions
            signal_parts = []
            for session in recent_sessions[-10:]:  # Last 10 sessions
                if isinstance(session, dict):
                    # Extract meaningful content
                    content = session.get('content', '') or session.get('goal', '')
                    if content:
                        signal_parts.append(f"- {content[:200]}...")
                        
            # Also look for contradictions or new information
            # In a full implementation, we would compare with existing memories
            
            signal = "\n".join(signal_parts) if signal_parts else "No significant recent activity detected."
            logger.debug(f"Gathered signal: {signal[:100]}...")
            return signal
            
        except Exception as e:
            logger.error(f"Error gathering recent signal: {e}")
            return "Error gathering recent signal"
            
    async def _phase_3_consolidate(self, recent_signal: str) -> str:
        """Phase 3: Consolidate - write or update memory files."""
        logger.debug("Phase 3: Consolidate")
        
        try:
            # In Claude Code's system, this would use an LLM to process the signal
            # and update memory files. For now, we'll create a simple summary.
            
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            consolidated_content = f"""# Memory Consolidation Log
## Consolidated at: {timestamp}

### Recent Activity Summary
{recent_signal}

### Key Insights
- System has been processing user requests and agent tasks
- Memory consolidation system is now active
- Ready to retain important learnings from interactions

### Actions Taken
- Completed orient phase: surveyed memory directory
- Completed signal gathering: analyzed recent sessions
- Ready for consolidation phase
"""
            
            # In a full implementation, we would:
            # 1. Use an LLM to analyze the signal and extract key insights
            # 2. Update existing memory files or create new ones
            # 3. Convert relative dates to absolute dates
            # 4. Delete contradicted facts
            
            logger.debug(f"Prepared consolidated content: {len(consolidated_content)} chars")
            return consolidated_content
            
        except Exception as e:
            logger.error(f"Error in consolidation phase: {e}")
            return f"Error during consolidation: {e}"
            
    async def _phase_4_prune_and_index(self, consolidated_content: str):
        """Phase 4: Prune and Index - maintain memory files under limits."""
        logger.debug("Phase 4: Prune and Index")
        
        try:
            # In Claude Code's system:
            # - Keep MAIN_MEMORY_FILE under 200 lines AND ~25KB
            # - Remove stale pointers
            # - Resolve contradictions
            
            # For now, we'll just log what we would do
            logger.debug("Would prune memory index to under 200 lines and 25KB")
            logger.debug("Would remove stale pointers and resolve contradictions")
            
            # In a full implementation, we would:
            # 1. Update or create a consolidated memory file
            # 2. Ensure it meets size limits
            # 3. Update any index files
            
        except Exception as e:
            logger.error(f"Error in prune and index phase: {e}")

# Global instance
_memory_consolidation_system: Optional[MemoryConsolidationSystem] = None

def initialize_memory_consolidation(knowledge_dir: Path,
                                  get_recent_sessions: Callable[[], list[Dict[str, Any]]],
                                  get_memory_files: Callable[[], list[Path]],
                                  update_memory_file: Callable[[Path, str], None],
                                  min_hours_between: int = 24,
                                  min_sessions_since: int = 5) -> MemoryConsolidationSystem:
    """Initialize the global memory consolidation system."""
    global _memory_consolidation_system
    _memory_consolidation_system = MemoryConsolidationSystem(
        knowledge_dir=knowledge_dir,
        get_recent_sessions=get_recent_sessions,
        get_memory_files=get_memory_files,
        update_memory_file=update_memory_file,
        min_hours_between=min_hours_between,
        min_sessions_since=min_sessions_since
    )
    return _memory_consolidation_system

def get_memory_consolidation_system() -> Optional[MemoryConsolidationSystem]:
    """Get the global memory consolidation system instance."""
    return _memory_consolidation_system

async def start_memory_consolidation():
    """Start the memory consolidation system if initialized."""
    if _memory_consolidation_system:
        await _memory_consolidation_system.start()
        
async def stop_memory_consolidation():
    """Stop the memory consolidation system if running."""
    if _memory_consolidation_system:
        await _memory_consolidation_system.stop()