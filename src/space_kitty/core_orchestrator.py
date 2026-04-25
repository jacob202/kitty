"""
Core Space Kitty orchestrator.
Wires together: DomainRouter → Specialists → LLM + Knowledge Bases
Plus: Personality, Journal, Checkpoint, Honcho (psychological modeling)
Plus: Voice (Piper TTS + Whisper STT)
"""

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import numpy as np

from src.core.context_manager import ContextManager
from src.core.domain_router import Domain, DomainRouter
from src.core.specialist_framework import SpecialistRegistry, SpecialistResponse
from src.space_kitty.checkpoint_manager import CheckpointManager
from src.space_kitty.personality import KittyPersonality
from src.space_kitty.reasoning_layer import ReasoningLayer

# Frontend to Backend Domain Mapping
FRONTEND_MAPPING = {
    "chat": Domain.GENERAL,
    "auto": Domain.AUTOMOTIVE,
    "audio": Domain.AUDIO,
    "fitness": Domain.FITNESS,
    "growth": Domain.GROWTH,
    "code": Domain.CODE,
    "journal": Domain.SOUL,
}

# Wiki memory (LLM Wiki pattern)
try:
    from src.memory.wiki_memory import wiki_memory
    WIKI_AVAILABLE = True
except ImportError:
    WIKI_AVAILABLE = False
    wiki_memory = None

# Voice components (optional - fail gracefully if not installed)
try:
    from src.voice.kitty_ears import KittyEars
    from src.voice.kitty_voice import KittyVoice
    from src.voice.voice_session import VoiceSession

    VOICE_AVAILABLE = True
except ImportError as e:
    VOICE_AVAILABLE = False
    VOICE_IMPORT_ERROR = str(e)

logger = logging.getLogger(__name__)


class CoreOrchestrator:
    """
    Main orchestration engine for Space Kitty.

    Flow:
      user query → DomainRouter (classify) → Specialist (query LLM + KB)
      → log to journal → analyze with Honcho → checkpoint state
    """

    def __init__(
        self,
        stt_model: str = "base",
        voice: str = "lessac",
        socketio: Any = None,
        enable_voice_components: bool = True,
    ):
        self.personality = KittyPersonality()
        self.domain_router = DomainRouter()
        self.specialists = SpecialistRegistry()
        self.checkpoint = CheckpointManager()
        self.context_manager = ContextManager()
        self.socketio = socketio
        self._conversation_history: list[dict[str, str]] = []
        self._bg_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="kitty-bg")
        self._cost_router = None
        self._last_checkpoint = None

        # Auto-resume from most recent session
        self._last_checkpoint = self.resume_from_checkpoint()
        if self._last_checkpoint:
            hist = self._last_checkpoint.get("state", {}).get("history", [])
            logger.info("Resumed session: %d messages from %s", len(hist), self._last_checkpoint.get("session_id"))

        # Reasoning layer
        self.reasoning = ReasoningLayer(
            emit_callback=self._emit_reasoning_progress if socketio else None
        )

        # Voice components (Piper TTS + Whisper STT)
        if enable_voice_components and VOICE_AVAILABLE:
            self.ears = KittyEars(model_size=stt_model)
            self.voice = KittyVoice(voice=voice)
        else:
            self.ears = None
            self.voice = None

    def process(
        self,
        query: str,
        context: dict | None = None,
        domain: str | None = None,
        mode: str | None = None,
        reasoning: bool = False,
        model_target: str | None = None,
    ) -> SpecialistResponse:
        """
        Process a user query end-to-end:
        1. Log to journal
        2. Route to domain specialist
        3. Get specialist response (LLM + knowledge base)
        4. Run Honcho psychological analysis
        5. Checkpoint state
        6. Return response
        """
        if isinstance(query, str) and query.startswith("/"):
            tool_response = self._process_slash_command(query)
            if tool_response is not None:
                return tool_response

        self.context_manager.journal.log("user", query)
        self._conversation_history.append({"role": "user", "content": query})
        self._trim_conversation_history()

        # Route to domain - use provided domain if valid, else auto-route
        routing = None

        if domain:
            try:
                # 1. Check mapping
                mapped_domain = FRONTEND_MAPPING.get(domain.lower())
                if mapped_domain:
                    routing = self.domain_router.get_routing_for_domain(mapped_domain)
                else:
                    # 2. Try direct Enum match
                    for d in Domain:
                        if d.value == domain:
                            routing = self.domain_router.get_routing_for_domain(d)
                            break
            except Exception as e:
                from src.core.exceptions import handle_exception
                handle_exception(e, context="orchestrator.domain_mapping", silent=True)

        if not routing:
            routing = self.domain_router.route(query)

        logger.info(
            f"Routed to {routing.specialist} ({routing.domain.value}) confidence={routing.confidence:.0%}"
        )
        self.context_manager.journal.log(
            "system", f"routed:{routing.specialist}|{routing.domain.value}|{routing.confidence:.2f}"
        )

        try:
            from src.api.emitters import emit_thinking_bubble
            emit_thinking_bubble(
                f"Routing to {routing.specialist} [{routing.domain.value}]",
                routing.confidence,
            )
        except Exception:
            pass

        # Reasoning layer: structured thinking before responding
        honcho_approach = self.context_manager.honcho.get_approach_recommendation()
        personality_ctx = self.personality.get_system_context() or ""
        reasoning_trace = self.reasoning.reason(
            query=query,
            domain=routing.domain.value,
            context=context,
            honcho_approach=honcho_approach,
            personality_context=personality_ctx,
        )

        if reasoning_trace and reasoning_trace.conclusion:
            try:
                from src.api.emitters import emit_thinking_bubble
                emit_thinking_bubble(
                    reasoning_trace.conclusion[:140],
                    min(1.0, routing.confidence + 0.05),
                )
            except Exception:
                pass

        # 1. Capture context snapshot using thread pool (reuses threads)
        self._bg_executor.submit(
            self.context_manager.correction_memory.capture_context_snapshot,
            query, routing.domain.value
        )

        # 2. Get Wiki context if available and relevant
        wiki_ctx_raw = ""
        if WIKI_AVAILABLE and wiki_memory:
            wiki_results = wiki_memory.search(query)
            if wiki_results:
                for page in wiki_results[:2]:
                    wiki_ctx_raw += f"From wiki ({page.title}):\n{page.content[:500]}\n"

        # 3. Build unified context preamble (budgeted integration of all signals)
        context_preamble = self.context_manager.build_unified_context(
            query=query,
            domain=routing.domain.value,
            recent_history=self._conversation_history,
            reasoning_conclusion=reasoning_trace.conclusion,
            wiki_context=wiki_ctx_raw.strip() if wiki_ctx_raw else None
        )

        # Select model via 3-decision router
        model = self._select_model(
            query,
            mode=mode,
            reasoning=reasoning,
            model_target=model_target,
        )
        logger.info(f"Model selected: {model}")

        # Get specialist response
        council_domain = getattr(Domain, "COUNCIL", None)
        if council_domain is not None and routing.domain == council_domain:
            from src.orchestrator.specialist_council import SpecialistCouncil

            # Identify relevant specialists using semantic similarity
            relevant_specialists = []
            if self.domain_router.semantic_router:
                try:
                    query_embedding = self.domain_router.semantic_router.model.encode(query)
                    similarities = []
                    for name, spec in self.specialists.specialists.items():
                        if name == "Kitty":
                            continue
                        spec_embedding = self.domain_router.semantic_router.model.encode(
                            f"{spec.domain} {spec.personality}"
                        )
                        sim = np.dot(query_embedding, spec_embedding) / (
                            np.linalg.norm(query_embedding) * np.linalg.norm(spec_embedding)
                        )
                        similarities.append((sim, spec))

                    # Take top 2-3 relevant specialists
                    similarities.sort(key=lambda x: x[0], reverse=True)
                    relevant_specialists = [s[1] for s in similarities[:3] if s[0] > 0.2]
                except Exception:
                    relevant_specialists = list(self.specialists.specialists.values())[:3]

            if not relevant_specialists:
                relevant_specialists = list(self.specialists.specialists.values())[:3]

            council = SpecialistCouncil(
                specialists=relevant_specialists,
                synthesizer_model=model
            )
            response = council.consult(
                query,
                context or {},
                model=model,
                context_preamble=context_preamble,
                honcho_approach=honcho_approach
            )
        else:
            specialist = self.specialists.get_specialist(routing.specialist)
            if specialist:
                response = specialist.query(
                    query,
                    context or {},
                    model=model,
                    context_preamble=context_preamble,
                    honcho_approach=honcho_approach
                )
            else:
                # Fallback: use general Kitty response via LLM
                response = self._general_response(
                    query,
                    context,
                    model=model,
                    confidence=routing.confidence,
                    context_preamble=context_preamble,
                    honcho_approach=honcho_approach
                )

        # Log response
        self.context_manager.journal.log("assistant", response.content)
        self._conversation_history.append({"role": "assistant", "content": response.content})
        self._trim_conversation_history()

        # Attach routing metadata to diagnostics
        if response.diagnostics is None:
            response.diagnostics = {}

        response.diagnostics.update({
            "routing": {
                "domain": routing.domain.value,
                "specialist": routing.specialist,
                "confidence": routing.confidence,
                "reasoning": routing.reasoning,
            },
            "reasoning_trace_id": reasoning_trace.id,
        })

        # Attach sentiment diagnostics if snapshot available
        latest_snaps = self.context_manager.correction_memory.get_recent_snapshots(days=1, limit=1)
        if latest_snaps:
            sentiment = latest_snaps[0].get("sentiment", 0.0)
            response.diagnostics["sentiment"] = sentiment

        # Honcho: psychological modeling
        self.context_manager.honcho.analyze_conversation(self._conversation_history)

        # Affective UI: broadcast state to frontend
        if self.socketio:
            try:
                from src.api.socket_handlers import emit_psychological_state
                emit_psychological_state(self.socketio)
            except ImportError:
                pass # SocketIO not available

        # Mood detection + checkpoint
        mood = self.personality.detect_mood(self._conversation_history)
        self.context_manager.journal.log("system", f"mood:{mood}")
        self.checkpoint.save_mood(mood)
        self.checkpoint.save_checkpoint(
            history=self._conversation_history,
            active_jobs=[],
            mood=mood,
        )

        return response

    def _select_model(
        self,
        query: str,
        mode: str | None = None,
        reasoning: bool = False,
        model_target: str | None = None,
    ) -> str | None:
        """Model router using CostRouter. Returns OpenRouter model ID or None for local."""
        import os

        from src.core.cost_router import CostRouter, ModelTier

        # Explicit web preferences override the cost router so the UI behaves predictably.
        if mode or model_target:
            if not os.getenv("OPENROUTER_API_KEY"):
                return None

            selected_mode = (mode or "balanced").lower()
            selected_target = (model_target or "configured").lower()
            configured_model = os.getenv("KITTY_MODEL", "openrouter/free")
            balanced_reason_model = os.getenv(
                "KITTY_BALANCED_REASON",
                "deepseek/deepseek-r1-distill-qwen-7b",
            )
            max_model = os.getenv("KITTY_MAX_MODEL", "deepseek/deepseek-r1-0528")

            if selected_target == "local":
                return None
            if selected_mode == "max":
                return max_model
            if selected_target == "free":
                return "openrouter/free"
            if selected_mode == "balanced" and reasoning:
                return balanced_reason_model
            return configured_model

        # No API key — let llm_client fall through to local MLX
        if not os.getenv("OPENROUTER_API_KEY"):
            return None

        # Cache CostRouter instance to avoid per-query file I/O
        if self._cost_router is None:
            self._cost_router = CostRouter()
        decision = self._cost_router.route(query)

        logger.info(f"CostRouter decision: {decision.tier.value} tier -> {decision.model} ({decision.provider})")
        if decision.warnings:
            for w in decision.warnings:
                logger.warning(f"CostRouter: {w}")

        if decision.tier in (ModelTier.FREE, ModelTier.CHEAP) or decision.provider == "mlx":
            return None  # fall through to local MLX in llm_client

        return decision.model

    def _general_response(
        self,
        query: str,
        context: dict | None = None,
        model: str | None = None,
        confidence: float = 0.5,
        context_preamble: str = "",
        honcho_approach: str = "",
    ) -> SpecialistResponse:
        """Fallback response when no specialist matches."""
        try:
            from src.space_kitty.llm_client import call_llm

            soul = self.personality.get_system_context()
            system_prompt = soul if soul else "You are Kitty. Direct, warm, budget-conscious. No bullshit."

            # Inject Honcho approach
            if honcho_approach:
                system_prompt = f"{system_prompt}\n\n[Current tone & strategy recommendation: {honcho_approach}]"

            if context_preamble:
                system_prompt = context_preamble + "\n\n" + system_prompt

            content = call_llm(
                prompt=query,
                system_prompt=system_prompt,
                model=model,
            )
        except Exception:
            content = "I hear you. Can you tell me a bit more?"

        return SpecialistResponse(
            content=content,
            confidence=confidence,
            sources=[],
            safety_warnings=[],
            suggested_followups=[],
            diagnostics={
                "specialist": "Kitty",
                "domain": "general",
                "emotional_adaptation": bool(honcho_approach)
            }
        )


    def _emit_reasoning_progress(self, data: dict):
        """Emit reasoning progress to frontend via WebSocket."""
        if self.socketio:
            try:
                self.socketio.emit("reasoning_progress", data)
            except Exception:
                pass

    def _trim_conversation_history(self, max_turns: int = 100):
        """Keep conversation history bounded to prevent memory growth."""
        if len(self._conversation_history) > max_turns:
            self._conversation_history = self._conversation_history[-max_turns:]

    def _process_slash_command(self, query: str) -> SpecialistResponse | None:
        """Handle local slash commands before routing to an LLM."""
        from src.tools.tool_manager import get_tool_manager

        manager = get_tool_manager()

        # Check if the command exists and if it requires confirmation
        parts = query.strip().split(maxsplit=1)
        if not parts:
            return None

        tool = manager.get_tool_by_command(parts[0].lower())
        if tool and tool.requires_confirmation:
            # Check for explicit confirmation flag (e.g. /write file.txt --confirm)
            if "--confirm" not in query:
                return SpecialistResponse(
                    content=f"⚠️ This action requires explicit confirmation. Please append '--confirm' to your command: {query}",
                    confidence=1.0,
                    sources=[],
                    safety_warnings=[f"User confirmation required for {tool.name}"],
                    suggested_followups=[]
                )

        tool_result = manager.execute_command(query)

        if not tool_result:
            return None

        # Format ToolResult as SpecialistResponse
        content = ""
        if tool_result.ok:
            if tool_result.tool == "list_directory":
                entries = "\n".join(tool_result.result.get("entries", []))
                content = f"Directory listing:\n{entries}" if entries else "Directory listing: empty"
            elif tool_result.tool == "read_file":
                content = tool_result.result.get("content", "")
            elif tool_result.tool == "search_files":
                matches = tool_result.result.get("matches", [])
                if not matches:
                    content = "No matches found"
                else:
                    lines = [
                        f"{match['file']}:{match['line']}: {match['text']}"
                        for match in matches
                    ]
                    content = "Found matches:\n" + "\n".join(lines)
        else:
            content = f"Error executing {tool_result.tool}: {tool_result.error}"

        return SpecialistResponse(
            content=content,
            confidence=1.0 if tool_result.ok else 0.0,
            sources=[],
            safety_warnings=[],
            suggested_followups=[],
            diagnostics={
                "tool_used": tool_result.tool,
                "ok": tool_result.ok,
                "denied": tool_result.denied,
            }
        )

    def get_approach(self) -> str:
        """Get Honcho's recommendation for how to communicate right now."""
        return self.context_manager.honcho.get_approach_recommendation()

    def get_psychological_state(self) -> dict[str, Any]:
        """Get current psychological model from Honcho."""
        return self.context_manager.honcho.get_current_state()

    def log_response(self, response: str):
        """Log an external response (e.g., from Supervisor)."""
        self.context_manager.journal.log("assistant", response)
        self._conversation_history.append({"role": "assistant", "content": response})

    def detect_patterns(self) -> list[str]:
        """Detect behavioral patterns from journal."""
        return self.context_manager.journal.detect_patterns()

    def get_status(self) -> dict[str, Any]:
        """Get full orchestrator status."""
        patterns = self.detect_patterns()
        mood = self.checkpoint.get_last_mood() or "unknown"
        psych_state = self.context_manager.honcho.get_current_state()
        approach = self.context_manager.honcho.get_approach_recommendation()

        return {
            "personality": self.personality.get_patterns_summary(),
            "mood": mood,
            "conversation_size": len(self._conversation_history),
            "patterns_detected": patterns,
            "voice": self.personality.get_voice(),
            "psychological_state": psych_state,
            "approach_recommendation": approach,
            "specialists_available": self.specialists.list_specialists(),
        }

    def resume_from_checkpoint(self) -> dict[str, Any] | None:
        """Resume from most recent checkpoint after context cutoff."""
        checkpoint = self.checkpoint.get_last_checkpoint()
        if checkpoint:
            state = checkpoint.get("state", {})
            self._conversation_history = state.get("history", [])
            return checkpoint
        return None

    def get_resume_summary(self) -> str | None:
        """Get a human-readable summary of the resumed session."""
        if not self._last_checkpoint:
            return None
        state = self._last_checkpoint.get("state", {})
        hist = state.get("history", [])
        session_id = self._last_checkpoint.get("session_id", "unknown")
        msg_count = len(hist)
        mood = state.get("mood", "unknown")
        return f"Resumed session {session_id}: {msg_count} messages, mood={mood}"

    def get_conversation_summary(self, limit: int = 10) -> str:
        return self.context_manager.journal.get_summary(limit=limit)

    def search_journal(self, query: str) -> list[dict[str, str]]:
        return self.context_manager.journal.search(query)

    def voice_chat(self):
        """
        Start a voice chat session using Piper TTS + Whisper STT.

        Flow: Listen (Whisper) → Process (orchestrator) → Speak (Piper)

        Prerequisites:
            - Piper TTS: https://github.com/rhasspy/piper
            - Whisper STT: pip install faster-whisper pyaudio
        """
        if not VOICE_AVAILABLE:
            logger.error("Voice not available: %s", VOICE_IMPORT_ERROR)
            return

        if not self.ears or not self.voice:
            logger.error("Voice components not initialized")
            return

        if not self.ears.is_available() and not self.voice.is_available():
            logger.error("Voice not available - missing dependencies. Install: Piper TTS + Whisper STT")
            return

        def process_callback(text: str) -> str:
            """Process voice input through orchestrator"""
            response = self.process(text)
            return response.content

        session = VoiceSession(
            stt_model="base",
            voice="lessac",
            process_callback=process_callback,
        )

        logger.info("Starting voice chat via CoreOrchestrator...")
        session.start(continuous=True)

    def is_voice_available(self) -> bool:
        """Check if voice (TTS + STT) is available"""
        if not VOICE_AVAILABLE:
            return False
        return (
            self.ears is not None
            and self.ears.is_available()
            and self.voice is not None
            and self.voice.is_available()
        )

    def speak(self, text: str) -> bool:
        """
        Speak text using Piper TTS.

        Args:
            text: Text to speak

        Returns:
            True if successful
        """
        if not self.voice:
            logger.warning("Voice not initialized")
            return False
        return self.voice.speak(text)

    def listen(self, duration: int = 5) -> str:
        """
        Listen and transcribe speech using Whisper.

        Args:
            duration: Recording duration in seconds

        Returns:
            Transcribed text
        """
        if not self.ears:
            logger.warning("Ears not initialized")
            return "[Ears not initialized]"
        return self.ears.listen(duration=duration)
