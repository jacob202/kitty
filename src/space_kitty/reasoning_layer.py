"""
Reasoning Layer — structured thinking before responding.

Provides:
- Multi-step reasoning traces (observe → analyze → decide → plan)
- Confidence scoring per step
- WebSocket emission of thinking progress
- Persistent trace storage for review
"""

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

TRACES_DIR = Path("data/reasoning_traces")


@dataclass
class ReasoningStep:
    """One step in a reasoning chain."""
    step_type: str  # "observe", "analyze", "decide", "plan", "reflect"
    content: str
    confidence: float = 0.5
    timestamp: float = field(default_factory=time.time)


@dataclass
class ReasoningTrace:
    """A complete reasoning chain for one query."""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    query: str = ""
    domain: str = ""
    steps: list[ReasoningStep] = field(default_factory=list)
    conclusion: str = ""
    created_at: float = field(default_factory=time.time)
    metadata: dict = field(default_factory=dict)

    def add_step(self, step_type: str, content: str, confidence: float = 0.5):
        step = ReasoningStep(step_type=step_type, content=content, confidence=confidence)
        self.steps.append(step)
        return step

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "query": self.query,
            "domain": self.domain,
            "steps": [
                {
                    "step_type": s.step_type,
                    "content": s.content,
                    "confidence": s.confidence,
                    "timestamp": s.timestamp,
                }
                for s in self.steps
            ],
            "conclusion": self.conclusion,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }


class ReasoningLayer:
    """
    Structured reasoning before responding.

    Flow:
      1. Observe — extract key signals from query + context
      2. Analyze — identify patterns, risks, opportunities
      3. Decide — choose approach based on SOUL rules
      4. Plan — outline response structure
      5. Reflect — sanity-check against identity goals

    Emits progress via callback for real-time UI updates.
    """

    def __init__(self, emit_callback=None):
        self.emit_callback = emit_callback
        self._traces: list[ReasoningTrace] = []
        TRACES_DIR.mkdir(parents=True, exist_ok=True)

    def reason(
        self,
        query: str,
        domain: str = "general",
        context: dict | None = None,
        honcho_approach: str = "",
        personality_context: str = "",
    ) -> ReasoningTrace:
        """Run full reasoning chain. Returns trace with steps + conclusion."""
        trace = ReasoningTrace(query=query, domain=domain)
        trace.metadata["honcho_approach"] = honcho_approach
        trace.metadata["personality_context"] = personality_context[:200]

        # Step 1: Observe
        self._emit(trace, "thinking", "Reading the room...")
        observe_step = self._observe(query, domain, context or {})
        trace.add_step("observe", observe_step["content"], observe_step["confidence"])
        self._emit(trace, "step", observe_step)

        # Step 2: Analyze
        self._emit(trace, "thinking", "Connecting dots...")
        analyze_step = self._analyze(query, domain, context or {}, honcho_approach)
        trace.add_step("analyze", analyze_step["content"], analyze_step["confidence"])
        self._emit(trace, "step", analyze_step)

        # Step 3: Decide
        self._emit(trace, "thinking", "Choosing approach...")
        decide_step = self._decide(query, domain, honcho_approach, personality_context)
        trace.add_step("decide", decide_step["content"], decide_step["confidence"])
        self._emit(trace, "step", decide_step)

        # Step 4: Plan
        self._emit(trace, "thinking", "Structuring response...")
        plan_step = self._plan(query, domain, decide_step)
        trace.add_step("plan", plan_step["content"], plan_step["confidence"])
        self._emit(trace, "step", plan_step)

        # Step 5: Reflect
        self._emit(trace, "thinking", "Final check...")
        reflect_step = self._reflect(query, domain, trace.steps)
        trace.add_step("reflect", reflect_step["content"], reflect_step["confidence"])
        self._emit(trace, "step", reflect_step)

        # Conclusion
        trace.conclusion = self._build_conclusion(trace.steps)
        self._emit(trace, "done", trace.conclusion)

        # Persist
        self._traces.append(trace)
        self._save_trace(trace)

        return trace

    def _observe(self, query: str, domain: str, context: dict) -> dict:
        """Extract key signals from the query."""
        signals = []

        # Domain context
        signals.append(f"Domain: {domain}")

        # Query characteristics
        is_question = query.rstrip().endswith("?")
        is_command = query.startswith("/")
        word_count = len(query.split())
        signals.append(f"Type: {'command' if is_command else 'question' if is_question else 'statement'} ({word_count} words)")

        # Emotional signals
        emotional_words = ["stuck", "tired", "overwhelmed", "confused", "excited", "worried", "anxious", "happy", "sad", "angry", "frustrated"]
        found_emotions = [w for w in emotional_words if w in query.lower()]
        if found_emotions:
            signals.append(f"Emotional signals: {', '.join(found_emotions)}")

        # Urgency signals
        urgency_words = ["urgent", "asap", "now", "immediately", "deadline", "rush"]
        found_urgency = [w for w in urgency_words if w in query.lower()]
        if found_urgency:
            signals.append(f"Urgency: {', '.join(found_urgency)}")

        # Context signals
        if context:
            signals.append(f"Context keys: {', '.join(context.keys())}")

        content = "\n".join(signals)
        confidence = 0.9 if signals else 0.5
        return {"content": content, "confidence": confidence}

    def _analyze(self, query: str, domain: str, context: dict, honcho_approach: str) -> dict:
        """Identify patterns, risks, and opportunities."""
        analysis = []

        # Pattern matching
        if "research" in query.lower() and "start" not in query.lower():
            analysis.append("Pattern: research loop risk — may need nudge toward action")

        if "plan" in query.lower() and "build" not in query.lower() and "ship" not in query.lower():
            analysis.append("Pattern: planning marathon risk — watch for architecture without implementation")

        # Domain-specific risks
        if domain in ("fitness", "growth", "journal"):
            analysis.append("Personal domain: 30-min rule applies — no plans, one action")
            if "figure out" in query.lower() or "decide" in query.lower():
                analysis.append("Risk: scope too large — will need to reframe to smallest step")

        # Honcho alignment
        if honcho_approach:
            analysis.append(f"Honcho strategy: {honcho_approach}")

        # Conflict detection
        avoidance_patterns = ["maybe later", "not now", "someday", "when I have time"]
        if any(p in query.lower() for p in avoidance_patterns):
            analysis.append("Conflict: avoidance language detected — check against stated goals")

        content = "\n".join(analysis) if analysis else "No significant patterns detected"
        confidence = 0.7 if analysis else 0.5
        return {"content": content, "confidence": confidence}

    def _decide(self, query: str, domain: str, honcho_approach: str, personality_context: str) -> dict:
        """Choose response approach based on SOUL rules."""
        decisions = []

        # 30-min rule
        if domain in ("fitness", "growth", "journal"):
            decisions.append("Apply 30-min rule: one concrete action, not a plan")

        # Emotional compression
        is_hyper_practical = any(w in query.lower() for w in ["how do i fix", "what's the best way", "steps to"])
        if is_hyper_practical and domain in ("growth", "journal"):
            decisions.append("Emotional compression possible: slow down, ask what it's costing")

        # Voice texture
        decisions.append("Voice: warm, direct, no bullshit — witness don't cheerlead")

        # Safety
        safety_words = ["high voltage", "mains", "capacitor", "brake", "airbag"]
        if any(w in query.lower() for w in safety_words):
            decisions.append("SAFETY: prefix dangerous advice with warning")

        content = "\n".join(decisions)
        confidence = 0.85
        return {"content": content, "confidence": confidence}

    def _plan(self, query: str, domain: str, decide_step: dict) -> dict:
        """Outline response structure."""
        plan = []

        if domain in ("fitness", "growth", "journal"):
            plan.append("1. Acknowledge the ask")
            plan.append("2. Reframe to one <30min action if needed")
            plan.append("3. Deliver compressed signal")
            plan.append("4. Invite expansion with 'more'")
        else:
            plan.append("1. Direct answer first")
            plan.append("2. Supporting details")
            plan.append("3. Safety warnings if applicable")
            plan.append("4. Next step suggestion")

        content = "\n".join(plan)
        confidence = 0.8
        return {"content": content, "confidence": confidence}

    def _reflect(self, query: str, domain: str, steps: list[ReasoningStep]) -> dict:
        """Sanity-check reasoning against identity goals."""
        checks = []

        # Does this serve the person?
        checks.append("Feature gate: does this serve the person, not just the task?")

        # Alive check
        checks.append("Alive check: would this feel like software or like a presence?")

        # No shame check
        checks.append("No shame: am I witnessing, not judging?")

        content = "\n".join(checks)
        confidence = 0.9
        return {"content": content, "confidence": confidence}

    def _build_conclusion(self, steps: list[ReasoningStep]) -> str:
        """Build a concise conclusion from reasoning steps."""
        observe = next((s for s in steps if s.step_type == "observe"), None)
        analyze = next((s for s in steps if s.step_type == "analyze"), None)
        decide = next((s for s in steps if s.step_type == "decide"), None)

        parts = []
        if observe:
            parts.append(f"Signals: {observe.content[:100]}")
        if analyze and analyze.content != "No significant patterns detected":
            parts.append(f"Patterns: {analyze.content[:100]}")
        if decide:
            parts.append(f"Approach: {decide.content[:100]}")

        return "\n".join(parts) if parts else "Reasoning complete"

    def _emit(self, trace: ReasoningTrace, event_type: str, data: Any):
        """Emit reasoning progress to callback."""
        if self.emit_callback:
            try:
                self.emit_callback({
                    "trace_id": trace.id,
                    "event": event_type,
                    "data": data,
                    "timestamp": time.time(),
                })
            except Exception as e:
                logger.debug(f"Reasoning emit failed: {e}")

    def _save_trace(self, trace: ReasoningTrace):
        """Persist reasoning trace to disk."""
        try:
            path = TRACES_DIR / f"{trace.id}.json"
            path.write_text(json.dumps(trace.to_dict(), indent=2))
        except Exception as e:
            logger.debug(f"Trace save failed: {e}")

    def get_recent_traces(self, limit: int = 10) -> list[dict]:
        """Get most recent reasoning traces."""
        traces = sorted(self._traces, key=lambda t: t.created_at, reverse=True)
        return [t.to_dict() for t in traces[:limit]]

    def get_trace(self, trace_id: str) -> dict | None:
        """Get a specific trace by ID."""
        for t in self._traces:
            if t.id == trace_id:
                return t.to_dict()
        # Try loading from disk
        path = TRACES_DIR / f"{trace_id}.json"
        if path.exists():
            return json.loads(path.read_text())
        return None

    def clear_traces(self, older_than_hours: float = 24):
        """Clear traces older than specified hours."""
        cutoff = time.time() - (older_than_hours * 3600)
        self._traces = [t for t in self._traces if t.created_at > cutoff]

        # Clean disk
        for path in TRACES_DIR.glob("*.json"):
            try:
                data = json.loads(path.read_text())
                if data.get("created_at", 0) < cutoff:
                    path.unlink()
            except Exception:
                pass
