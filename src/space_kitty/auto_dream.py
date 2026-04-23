"""
autoDream Protocol for Kitty - Background Memory Consolidation.

When terminal is idle for 5+ minutes, triggers consolidation:
1. Uses cheap local Ollama model (llama3.2:3b) to read raw chat logs
2. Extracts facts, preferences, successful commands
3. Pushes to ChromaDB for long-term storage
4. Wipes active short-term memory buffer
"""

import json
import logging
import os
import sqlite3
import threading
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from queue import Queue
from typing import Any

import requests

logger = logging.getLogger(__name__)

# ============================================================================
# Configuration
# ============================================================================

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
IDLE_THRESHOLD_SECONDS = int(os.getenv("AUTO_DREAM_IDLE_THRESHOLD", "300"))  # 5 minutes default
CHROMA_DB_PATH = os.getenv("AUTO_DREAM_CHROMA_PATH", "data/auto_dream_chroma")
SHORT_TERM_BUFFER_PATH = os.getenv("AUTO_DREAM_BUFFER_PATH", "data/short_term_buffer.db")


# ============================================================================
# IdleDetector - Tracks Terminal Activity
# ============================================================================


class IdleDetector:
    """
    Tracks terminal activity to detect idle periods.

    Uses multiple signals:
    - Journal activity (conversation logs)
    - Checkpoint updates
    - Manual activity signals

    Safe: only triggers when truly idle, not during user activity.
    """

    def __init__(self, idle_threshold_seconds: int = IDLE_THRESHOLD_SECONDS):
        self.idle_threshold = idle_threshold_seconds
        self._last_activity_time: float = time.time()
        self._activity_lock = threading.Lock()
        self._journal_path = Path("data/journal.db")

    def record_activity(self, activity_type: str = "generic") -> None:
        """Record user or system activity."""
        with self._activity_lock:
            self._last_activity_time = time.time()
            logger.debug(f"Activity recorded: {activity_type}")

    def is_idle(self) -> bool:
        """Check if terminal has been idle for threshold duration."""
        with self._activity_lock:
            idle_duration = time.time() - self._last_activity_time
            return idle_duration >= self.idle_threshold

    def get_idle_duration(self) -> float:
        """Get current idle duration in seconds."""
        with self._activity_lock:
            return time.time() - self._last_activity_time

    def reset_idle_timer(self) -> None:
        """Manually reset the idle timer."""
        self.record_activity("manual_reset")

    def check_journal_idle(self) -> bool:
        """
        Check if journal has been silent (supplemental idle check).
        Prevents false triggers if system is busy but activity not recorded.
        """
        if not self._journal_path.exists():
            return True

        try:
            with sqlite3.connect(str(self._journal_path)) as conn:
                cursor = conn.execute("SELECT timestamp FROM journal ORDER BY id DESC LIMIT 1")
                row = cursor.fetchone()
                if not row:
                    return True

                last_journal_time = datetime.fromisoformat(row[0])
                idle_minutes = (datetime.now() - last_journal_time).total_seconds() / 60
                return idle_minutes >= (self.idle_threshold / 60)
        except Exception as e:
            logger.warning(f"Could not check journal idle: {e}")
            return False


# ============================================================================
# ShortTermBuffer - Active Memory Store
# ============================================================================


@dataclass
class MemoryItem:
    """A single memory item in the short-term buffer."""

    id: str
    role: str  # 'user' or 'assistant'
    content: str
    timestamp: str
    extracted: bool = False  # Has this been processed by consolidation?

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ShortTermBuffer:
    """
    Manages the active short-term memory buffer.
    This buffer holds recent conversation items pending consolidation.
    """

    def __init__(self, db_path: str = SHORT_TERM_BUFFER_PATH):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self) -> None:
        """Initialize the buffer database."""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS short_term_buffer (
                    id TEXT PRIMARY KEY,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    extracted INTEGER DEFAULT 0
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_timestamp
                ON short_term_buffer(timestamp)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_extracted
                ON short_term_buffer(extracted)
            """)
            conn.commit()

    def add(self, role: str, content: str) -> str:
        """Add a memory item to the buffer."""
        import uuid

        item_id = str(uuid.uuid4())[:12]
        timestamp = datetime.now().isoformat()

        with self._lock:
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.execute(
                    """INSERT INTO short_term_buffer
                       (id, role, content, timestamp, extracted)
                       VALUES (?, ?, ?, ?, 0)""",
                    (item_id, role, content, timestamp),
                )
                conn.commit()

        logger.debug(f"Added to buffer: {item_id} ({role})")
        return item_id

    def get_pending_items(self, limit: int = 100) -> list[MemoryItem]:
        """Get items that haven't been extracted yet."""
        with self._lock:
            with sqlite3.connect(str(self.db_path)) as conn:
                rows = conn.execute(
                    """SELECT id, role, content, timestamp, extracted
                       FROM short_term_buffer
                       WHERE extracted = 0
                       ORDER BY timestamp ASC
                       LIMIT ?""",
                    (limit,),
                ).fetchall()

        return [
            MemoryItem(id=r[0], role=r[1], content=r[2], timestamp=r[3], extracted=bool(r[4]))
            for r in rows
        ]

    def mark_extracted(self, item_ids: list[str]) -> int:
        """Mark items as extracted."""
        if not item_ids:
            return 0

        with self._lock:
            with sqlite3.connect(str(self.db_path)) as conn:
                placeholders = ",".join("?" * len(item_ids))
                cursor = conn.execute(
                    f"UPDATE short_term_buffer SET extracted = 1 WHERE id IN ({placeholders})",
                    item_ids,
                )
                conn.commit()
                return cursor.rowcount

    def wipe_all(self) -> int:
        """Wipe all items from the buffer (after successful consolidation)."""
        with self._lock:
            with sqlite3.connect(str(self.db_path)) as conn:
                cursor = conn.execute("DELETE FROM short_term_buffer")
                conn.commit()
                count = cursor.rowcount

        logger.info(f"Wiped {count} items from short-term buffer")
        return count

    def get_count(self) -> int:
        """Get total item count in buffer."""
        with self._lock:
            with sqlite3.connect(str(self.db_path)) as conn:
                cursor = conn.execute("SELECT COUNT(*) FROM short_term_buffer")
                return cursor.fetchone()[0]

    def get_pending_count(self) -> int:
        """Get count of pending (unextracted) items."""
        with self._lock:
            with sqlite3.connect(str(self.db_path)) as conn:
                cursor = conn.execute("SELECT COUNT(*) FROM short_term_buffer WHERE extracted = 0")
                return cursor.fetchone()[0]


# ============================================================================
# ConsolidationAgent - Extracts Facts from Chat Logs
# ============================================================================

SYSTEM_PROMPT = """You are a memory consolidation agent. Your job is to extract MEANINGFUL information from conversation logs.

IGNORE (skip entirely):
- Casual greetings ("hi", "hello", "thanks", "please")
- Small talk and pleasantries
- Acknowledgments ("ok", "sure", "got it")
- Generic questions without specific context

EXTRACT (these matter):
1. FACTS: Specific knowledge shared (names, dates, numbers, technical details)
2. PREFERENCES: User likes/dislikes, work style, communication preferences
3. COMMANDS: Successful shell commands, git operations, tool usage patterns
4. DECISIONS: Choices made, trade-offs considered, conclusions reached
5. RELATIONSHIPS: How things connect (file X depends on Y, service Z uses port 8080)
6. ERRORS_LEARNED: What failed and why, how it was fixed

Output ONLY valid JSON. No markdown, no explanation, just JSON array of objects.
Each object has:
- "type": "fact" | "preference" | "command" | "decision" | "relationship" | "error_learned"
- "content": The extracted information (concise, factual)
- "confidence": 0.0-1.0 (how certain you are this matters)

Example output:
[
  {"type": "fact", "content": "User prefers dark mode terminal", "confidence": 0.9},
  {"type": "command", "content": "git push -u origin feature-branch", "confidence": 1.0},
  {"type": "preference", "content": "User不喜欢复杂的命令行参数", "confidence": 0.85}
]

Only output the JSON array. No preamble."""


class ConsolidationAgent:
    """
    Uses llama3.2:3b to extract meaningful facts from chat logs.
    Cheap to run locally, extracts hard facts from casual conversation.
    """

    def __init__(self, model: str = OLLAMA_MODEL):
        self.model = model
        self.ollama_url = OLLAMA_URL

    def extract(self, conversation_text: str) -> list[dict[str, Any]]:
        """
        Extract facts from conversation text using Ollama.

        Args:
            conversation_text: Raw conversation log to analyze

        Returns:
            List of extracted facts/preferences/commands
        """
        if not conversation_text.strip():
            return []

        try:
            response = self._call_ollama(conversation_text)
            return self._parse_response(response)
        except Exception as e:
            logger.error(f"Consolidation extraction failed: {e}")
            return []

    def _call_ollama(self, prompt: str) -> str:
        """Call Ollama API for extraction."""
        try:
            resp = requests.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "system": SYSTEM_PROMPT,
                    "stream": False,
                    "options": {
                        "temperature": 0.3,  # Low temp for factual extraction
                        "num_predict": 1024,  # Limit response length
                    },
                },
                timeout=120,  # 2 minute timeout for extraction
            )
            resp.raise_for_status()
            return resp.json().get("response", "").strip()
        except requests.exceptions.Timeout:
            logger.warning("Ollama extraction timed out")
            raise
        except requests.exceptions.ConnectionError:
            logger.warning("Ollama not available at %s", self.ollama_url)
            raise
        except Exception as e:
            logger.error(f"Ollama call failed: {e}")
            raise

    def _parse_response(self, response: str) -> list[dict[str, Any]]:
        """Parse JSON response from Ollama."""
        # Try to extract JSON from response (may have extra text)
        try:
            # Find JSON array in response
            start = response.find("[")
            end = response.rfind("]") + 1
            if start >= 0 and end > start:
                json_str = response[start:end]
                return json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse extraction response: {e}")
            logger.debug(f"Response was: {response[:200]}...")

        return []


# ============================================================================
# ChromaDB Storage - Long-term Memory Store
# ============================================================================


class LongTermMemoryStore:
    """
    ChromaDB-based long-term memory storage.
    Persists extracted facts for semantic retrieval.
    """

    def __init__(self, db_path: str = CHROMA_DB_PATH):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._collection_name = "auto_dream_memories"
        self._client = None
        self._collection = None
        self._init_chroma()

    def _init_chroma(self) -> None:
        """Initialize ChromaDB client and collection."""
        try:
            import chromadb
            from chromadb.config import Settings

            self._client = chromadb.PersistentClient(
                path=str(self.db_path),
                settings=Settings(
                    allow_reset=True,
                    anonymized_telemetry=False,
                ),
            )

            self._collection = self._client.get_or_create_collection(
                name=self._collection_name,
                metadata={"description": "autoDream Protocol long-term memories"},
            )
            logger.info(f"ChromaDB initialized at {self.db_path}")
        except ImportError:
            logger.error("ChromaDB not installed. Run: pip install chromadb")
            raise
        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB: {e}")
            raise

    def store(self, memories: list[dict[str, Any]], source_session: str = "unknown") -> int:
        """
        Store extracted memories in ChromaDB.

        Args:
            memories: List of extracted memory items
            source_session: Session identifier for tracing

        Returns:
            Number of memories stored
        """
        if not memories:
            return 0

        try:
            ids = []
            documents = []
            metadatas = []

            for i, memory in enumerate(memories):
                memory_id = f"dream_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{i}"

                ids.append(memory_id)
                documents.append(memory.get("content", ""))
                metadatas.append(
                    {
                        "type": memory.get("type", "unknown"),
                        "confidence": float(memory.get("confidence", 0.5)),
                        "source_session": source_session,
                        "extracted_at": datetime.now().isoformat(),
                    }
                )

            self._collection.upsert(
                ids=ids,
                documents=documents,
                metadatas=metadatas,
            )

            logger.info(f"Stored {len(memories)} memories in ChromaDB")
            return len(memories)

        except Exception as e:
            logger.error(f"Failed to store memories: {e}")
            raise

    def search(
        self, query: str, type_filter: str | None = None, limit: int = 10
    ) -> list[dict[str, Any]]:
        """
        Search long-term memories semantically.

        Args:
            query: Search query
            type_filter: Optional memory type filter
            limit: Max results

        Returns:
            List of matching memories
        """
        try:
            results = self._collection.query(
                query_texts=[query],
                n_results=limit * 2,  # Over-fetch for filtering
                include=["documents", "metadatas", "distances"],
            )

            memories = []
            for i in range(len(results["ids"][0])):
                memory = {
                    "id": results["ids"][0][i],
                    "content": results["documents"][0][i],
                    "type": results["metadatas"][0][i].get("type"),
                    "confidence": results["metadatas"][0][i].get("confidence"),
                    "distance": results["distances"][0][i],
                }

                # Apply type filter
                if type_filter and memory["type"] != type_filter:
                    continue

                memories.append(memory)

            return memories[:limit]

        except Exception as e:
            logger.error(f"Memory search failed: {e}")
            return []

    def count(self) -> int:
        """Get total memory count."""
        return self._collection.count()


# ============================================================================
# Dream Consolidation - Core Consolidation Logic
# ============================================================================


@dataclass
class ConsolidationResult:
    """Result of a consolidation run."""

    success: bool
    items_processed: int
    memories_stored: int
    duration_seconds: float
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class DreamConsolidator:
    """
    Orchestrates the memory consolidation process.
    Coordinates: Buffer → Agent → Storage
    """

    def __init__(
        self,
        buffer: ShortTermBuffer | None = None,
        agent: ConsolidationAgent | None = None,
        store: LongTermMemoryStore | None = None,
    ):
        self.buffer = buffer or ShortTermBuffer()
        self.agent = agent or ConsolidationAgent()
        self.store = store or LongTermMemoryStore()

    def reflect_on_feedback(self) -> int:
        """
        Review recent 'user_correction' events and generate correction tasks.
        Returns number of corrections processed.
        """
        try:
            from src.memory.memory_weave import get_weave
            weave = get_weave()

            # Find recent negative feedback
            events = weave.get_recent_events(event_type="user_correction", hours=48)
            neg_feedback = [e for e in events if e["description"] == "wrong"]

            if not neg_feedback:
                return 0

            logger.info(f"Dreaming: Reflecting on {len(neg_feedback)} negative feedback items...")

            # For each 'wrong' item, we could trigger a specific analysis
            # For now, we'll just log it as a pending correction task
            for item in neg_feedback:
                entity = item["entity"]
                logger.info(f"  - Correction needed for: {entity}")
                # We could call self.agent.analyze_correction() here

            return len(neg_feedback)
        except Exception as e:
            logger.error(f"Feedback reflection failed: {e}")
            return 0

    def consolidate(self, session_id: str = "unknown") -> ConsolidationResult:
        """
        Run consolidation cycle:
        1. Get pending items from buffer
        2. Extract facts using LLM
        3. Store in ChromaDB
        4. Reflect on feedback
        5. Wipe processed items
        """
        start_time = time.time()

        try:
            # Step 4: Reflect on feedback
            self.reflect_on_feedback()

            # Step 5: Apply RAG Fixes
            from src.memory.correction_worker import run_nightly_fixes
            applied_fixes = run_nightly_fixes()
            if applied_fixes > 0:
                logger.info(f"Dream Cycle: Applied {applied_fixes} RAG corrections.")

            # Step 6: Get pending items
            items = self.buffer.get_pending_items(limit=100)
            if not items:
                logger.info("No pending items to consolidate")
                return ConsolidationResult(
                    success=True,
                    items_processed=0,
                    memories_stored=0,
                    duration_seconds=time.time() - start_time,
                )

            logger.info(f"Consolidating {len(items)} items...")

            # Step 2: Format conversation for extraction
            conversation_text = self._format_conversation(items)

            # Step 3: Extract facts
            extracted = self.agent.extract(conversation_text)
            if not extracted:
                logger.warning("No facts extracted from conversation")
                # Still mark as processed to avoid reprocessing
                self.buffer.mark_extracted([item.id for item in items])
                return ConsolidationResult(
                    success=True,
                    items_processed=len(items),
                    memories_stored=0,
                    duration_seconds=time.time() - start_time,
                )

            # Step 4: Store in ChromaDB
            stored_count = self.store.store(extracted, source_session=session_id)

            # Step 5: Mark items as extracted
            self.buffer.mark_extracted([item.id for item in items])

            # Step 6: Wipe buffer (items already marked, safe to wipe)
            # We keep recent items in case of failure, wipe older ones
            if len(items) > 10:  # Only wipe if we have substantial content
                self.buffer.wipe_all()

            duration = time.time() - start_time
            logger.info(
                f"Consolidation complete: {len(items)} items → {stored_count} memories "
                f"in {duration:.1f}s"
            )

            return ConsolidationResult(
                success=True,
                items_processed=len(items),
                memories_stored=stored_count,
                duration_seconds=duration,
            )

        except Exception as e:
            logger.error(f"Consolidation failed: {e}")
            return ConsolidationResult(
                success=False,
                items_processed=0,
                memories_stored=0,
                duration_seconds=time.time() - start_time,
                error=str(e),
            )

    def _format_conversation(self, items: list[MemoryItem]) -> str:
        """Format memory items into conversation text for LLM."""
        lines = []
        for item in items:
            role_label = "User" if item.role == "user" else "Assistant"
            lines.append(f"{role_label}: {item.content}")
        return "\n\n".join(lines)


# ============================================================================
# autoDreamEngine - Main Protocol Controller
# ============================================================================


class ConsolidationEvent:
    """Event emitted during consolidation."""

    CONSOLIDATION_STARTED = "consolidation_started"
    CONSOLIDATION_COMPLETED = "consolidation_completed"
    CONSOLIDATION_FAILED = "consolidation_failed"
    IDLE_DETECTED = "idle_detected"


@dataclass
class autoDreamConfig:  # noqa: N801

    """Configuration for autoDream Protocol."""

    idle_threshold_seconds: int = IDLE_THRESHOLD_SECONDS
    check_interval_seconds: int = 30  # How often to check for idle
    enabled: bool = True
    auto_wipe_buffer: bool = True  # Wipe buffer after successful consolidation
    max_items_per_consolidation: int = 100


class autoDreamEngine:  # noqa: N801

    """
    Main autoDream Protocol engine.

    Runs in background thread, monitors for idle periods,
    and triggers memory consolidation automatically.

    Integration:
        engine = autoDreamEngine()
        engine.start()  # Start background monitoring

        # In your orchestrator:
        engine.record_activity()  # When user interacts

        engine.stop()  # Shutdown
    """

    def __init__(
        self,
        config: autoDreamConfig | None = None,
        idle_detector: IdleDetector | None = None,
        consolidator: DreamConsolidator | None = None,
    ):
        self.config = config or autoDreamConfig()
        self.idle_detector = idle_detector or IdleDetector(
            idle_threshold_seconds=self.config.idle_threshold_seconds
        )
        self.consolidator = consolidator or DreamConsolidator()

        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._consolidation_lock = threading.Lock()
        self._event_queue: Queue = Queue()
        self._is_running = False
        self._session_counter = 0

    def start(self) -> None:
        """Start the background idle monitoring thread."""
        if self._is_running:
            logger.warning("autoDream engine already running")
            return

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._monitor_loop,
            name="autoDream-Monitor",
            daemon=True,
        )
        self._thread.start()
        self._is_running = True
        logger.info(
            f"autoDream engine started (idle_threshold={self.config.idle_threshold_seconds}s)"
        )

    def stop(self) -> None:
        """Stop the background monitoring thread."""
        if not self._is_running:
            return

        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        self._is_running = False
        logger.info("autoDream engine stopped")

    def record_activity(self, activity_type: str = "generic") -> None:
        """
        Record terminal activity.
        Call this from CoreOrchestrator when user interacts.
        """
        self.idle_detector.record_activity(activity_type)

    def trigger_consolidation(self) -> ConsolidationResult:
        """
        Manually trigger consolidation.
        Thread-safe, can be called from any thread.
        """
        with self._consolidation_lock:
            self._session_counter += 1
            session_id = f"manual_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

            logger.info(f"Manual consolidation triggered (session: {session_id})")
            self._emit_event(ConsolidationEvent.CONSOLIDATION_STARTED, {"session_id": session_id})

            result = self.consolidator.consolidate(session_id=session_id)

            if result.success:
                self._emit_event(ConsolidationEvent.CONSOLIDATION_COMPLETED, result.to_dict())
            else:
                self._emit_event(ConsolidationEvent.CONSOLIDATION_FAILED, {"error": result.error})

            return result

    def get_status(self) -> dict[str, Any]:
        """Get current engine status."""
        buffer_count = self.consolidator.buffer.get_count()
        pending_count = self.consolidator.buffer.get_pending_count()
        memory_count = self.consolidator.store.count()

        return {
            "running": self._is_running,
            "idle_duration_seconds": self.idle_detector.get_idle_duration(),
            "idle_threshold_seconds": self.config.idle_threshold_seconds,
            "is_idle": self.idle_detector.is_idle(),
            "buffer_items": buffer_count,
            "pending_items": pending_count,
            "long_term_memories": memory_count,
            "enabled": self.config.enabled,
        }

    def get_recent_events(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get recent consolidation events."""
        events = []
        while not self._event_queue.empty() and len(events) < limit:
            try:
                events.append(self._event_queue.get_nowait())
            except Exception:
                break
        return events

    def _monitor_loop(self) -> None:
        """Background monitoring loop."""
        logger.info("autoDream monitor loop started")

        while not self._stop_event.is_set():
            try:
                if self.config.enabled:
                    self._check_and_consolidate()
            except Exception as e:
                logger.error(f"Monitor loop error: {e}")

            # Wait for next check interval or stop signal
            self._stop_event.wait(timeout=self.config.check_interval_seconds)

        logger.info("autoDream monitor loop ended")

    def _check_and_consolidate(self) -> None:
        """Check for idle and trigger consolidation if needed."""
        # Check both our timer and journal activity
        is_idle = self.idle_detector.is_idle() and self.idle_detector.check_journal_idle()

        if not is_idle:
            return

        # Check if there's work to do
        pending = self.consolidator.buffer.get_pending_count()
        if pending == 0:
            logger.debug("Idle but no pending items to consolidate")
            return

        logger.info(f"Idle detected, triggering consolidation ({pending} pending items)")
        self._emit_event(
            ConsolidationEvent.IDLE_DETECTED,
            {"pending_items": pending, "idle_duration": self.idle_detector.get_idle_duration()},
        )

        # Run consolidation (blocking, but in background thread)
        with self._consolidation_lock:
            self._session_counter += 1
            session_id = f"auto_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

            self._emit_event(ConsolidationEvent.CONSOLIDATION_STARTED, {"session_id": session_id})

            result = self.consolidator.consolidate(session_id=session_id)

            if result.success:
                self._emit_event(ConsolidationEvent.CONSOLIDATION_COMPLETED, result.to_dict())
            else:
                self._emit_event(ConsolidationEvent.CONSOLIDATION_FAILED, {"error": result.error})

    def _emit_event(self, event_type: str, data: dict[str, Any]) -> None:
        """Emit an event for external listeners."""
        event = {
            "type": event_type,
            "timestamp": datetime.now().isoformat(),
            "data": data,
        }
        self._event_queue.put(event)
        logger.debug(f"autoDream event: {event_type}")


# ============================================================================
# CoreOrchestrator Integration Hooks
# ============================================================================


def create_auto_dream_hook(engine: autoDreamEngine):
    """
    Create integration hooks for CoreOrchestrator.

    Usage:
        engine = autoDreamEngine()
        engine.start()

        # In your orchestrator:
        process_hooks = create_auto_dream_hook(engine)
        # process_hooks.record_activity() called after each user interaction
    """

    class autoDreamHooks:  # noqa: N801

        """Hooks for CoreOrchestrator integration."""

        def __init__(self, dream_engine: autoDreamEngine):
            self.engine = dream_engine

        def on_user_input(self, query: str) -> None:
            """Called when user sends input."""
            self.engine.record_activity("user_input")

        def on_assistant_response(self, response: str) -> None:
            """Called when assistant responds."""
            self.engine.record_activity("assistant_response")

        def on_tool_use(self, tool_name: str) -> None:
            """Called when a tool is used."""
            self.engine.record_activity(f"tool:{tool_name}")

        def on_checkpoint(self) -> None:
            """Called when checkpoint is saved."""
            self.engine.record_activity("checkpoint")

        def get_status(self) -> dict[str, Any]:
            """Get autoDream status."""
            return self.engine.get_status()

        def trigger_consolidation(self) -> ConsolidationResult:
            """Manually trigger consolidation."""
            return self.engine.trigger_consolidation()

    return autoDreamHooks(engine)


# ============================================================================
# Global Instance (lazy initialization)
# ============================================================================

_auto_dream_engine: autoDreamEngine | None = None


def get_auto_dream_engine() -> autoDreamEngine:
    """Get the global autoDream engine instance."""
    global _auto_dream_engine
    if _auto_dream_engine is None:
        _auto_dream_engine = autoDreamEngine()
    return _auto_dream_engine


def start_auto_dream() -> autoDreamEngine:
    """Start the autoDream engine and return the instance."""
    engine = get_auto_dream_engine()
    engine.start()
    return engine


def stop_auto_dream() -> None:
    """Stop the autoDream engine."""
    global _auto_dream_engine
    if _auto_dream_engine:
        _auto_dream_engine.stop()
        _auto_dream_engine = None


# ============================================================================
# CLI Interface
# ============================================================================


def main():
    """CLI for manual consolidation and status."""
    import argparse

    parser = argparse.ArgumentParser(description="autoDream Protocol CLI")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Status command
    subparsers.add_parser("status", help="Show autoDream status")

    # Consolidate command
    subparsers.add_parser("consolidate", help="Manually trigger consolidation")

    # Start command
    subparsers.add_parser("start", help="Start autoDream background engine")

    # Stop command
    subparsers.add_parser("stop", help="Stop autoDream background engine")

    # Buffer command
    subparsers.add_parser("buffer", help="Show short-term buffer status")

    args = parser.parse_args()

    if args.command == "status":
        engine = get_auto_dream_engine()
        status = engine.get_status()
        print(json.dumps(status, indent=2))

    elif args.command == "consolidate":
        engine = get_auto_dream_engine()
        result = engine.trigger_consolidation()
        print(json.dumps(result.to_dict(), indent=2))

    elif args.command == "start":
        engine = start_auto_dream()
        print("autoDream engine started")
        print(json.dumps(engine.get_status(), indent=2))

    elif args.command == "stop":
        stop_auto_dream()
        print("autoDream engine stopped")

    elif args.command == "buffer":
        buffer = ShortTermBuffer()
        pending = buffer.get_pending_items(limit=20)
        print(f"Total items: {buffer.get_count()}")
        print(f"Pending: {buffer.get_pending_count()}")
        print("\nRecent pending items:")
        for item in pending[:10]:
            preview = item.content[:80] + "..." if len(item.content) > 80 else item.content
            print(f"  [{item.role}] {preview}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
