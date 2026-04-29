"""Minimal CoreOrchestrator compatibility layer for web mode tests."""

from __future__ import annotations

import os
from typing import Any

from src.core.domain_router import DomainRouter
from src.core.specialist_framework import SpecialistResponse

try:
    from src.core.context_manager import ContextManager
except Exception:  # pragma: no cover - fallback for partial runtime setups
    ContextManager = object  # type: ignore[assignment]

try:
    from src.core.specialists.registry import get_specialist as find_specialist
except Exception:  # pragma: no cover
    def find_specialist(_name):
        return None

class SpecialistRegistry:
    def get_specialist(self, name):
        return find_specialist(name)


class CheckpointManager:
    def save_mood(self, *_args, **_kwargs):
        return None

    def save_checkpoint(self, **_kwargs):
        return None

    def get_last_checkpoint(self, **_kwargs):
        return None


class KittyPersonality:
    def get_system_context(self) -> str:
        return "You are Kitty."

    def detect_mood(self, *_args, **_kwargs) -> str:
        return "calm"


class ReasoningLayer:
    def __init__(self, emit_callback=None):
        self.emit_callback = emit_callback

    def reason(self, **_kwargs):
        return None


VOICE_AVAILABLE = False
FREE_ROUTER_MODEL = "deepseek/deepseek-v4-flash"


class CoreOrchestrator:
    """Small orchestrator facade retained for existing web wiring."""

    def __init__(self, socketio=None, enable_voice_components: bool = False):
        self.socketio = socketio
        self.enable_voice_components = enable_voice_components and VOICE_AVAILABLE
        self.context_manager = ContextManager()
        self.domain_router = DomainRouter()
        self.specialists = SpecialistRegistry()
        self.checkpoint_manager = CheckpointManager()
        self.personality = KittyPersonality()
        self.reasoning_layer = ReasoningLayer(emit_callback=self._emit_token)

    def _emit_token(self, text: str) -> None:
        if self.socketio is not None:
            self.socketio.emit("token", {"text": text})

    def get_resume_summary(self) -> str | None:
        checkpoint = None
        try:
            checkpoint = self.checkpoint_manager.get_last_checkpoint()
        except Exception:
            checkpoint = None
        if isinstance(checkpoint, str):
            return checkpoint
        if isinstance(checkpoint, dict):
            return checkpoint.get("summary") or checkpoint.get("text")
        return None

    def process(
        self,
        query: str,
        *,
        domain: str | None = None,
        context: str | None = None,
        mode: str = "fast",
        reasoning: bool = False,
        model_target: str | None = None,
    ) -> SpecialistResponse:
        try:
            # 1. Route to domain
            routed = self.domain_router.route(query)
            specialist_name = routed.specialist

            # 2. Get specialist
            specialist = self.specialists.get_specialist(specialist_name)

            # 3. Query specialist if available
            if specialist is not None:
                # Most specialists use .query() from BaseSpecialist
                response = specialist.query(query, context={"additional_context": context} if context else None)
                if response and getattr(response, "content", "").strip():
                    return response

        except Exception as e:
            logger.warning(f"Orchestrator routing failed: {e}")

        # Fallback to general LLM response instead of echoing
        return self._general_llm_response(query, context=context)

    def _general_llm_response(self, query: str, context: str | None = None) -> SpecialistResponse:
        from src.space_kitty.llm_client import call_llm

        system_prompt = self.personality.get_system_context()
        if context:
            system_prompt += f"\n\nContext:\n{context}"

        response_text = call_llm(prompt=query, system_prompt=system_prompt)
        
        # Return the exact response text, even if blank, to trigger dispatcher web fallback
        return SpecialistResponse(
            content=response_text or "",
            confidence=0.7,
            sources=[],
            safety_warnings=[],
            suggested_followups=[],
            diagnostics={"specialist": "Kitty"},
        )

    def _select_model(
        self,
        _query: str,
        *,
        mode: str = "fast",
        reasoning: bool = False,
        model_target: str | None = None,
    ) -> str | None:
        target = (model_target or "").lower()
        normalized_mode = (mode or "fast").lower()

        if normalized_mode == "fast":
            return FREE_ROUTER_MODEL
        if normalized_mode == "balanced":
            if target == "local":
                return None
            if reasoning:
                return os.environ.get("KITTY_BALANCED_REASON", "deepseek/deepseek-r1-distill-qwen-32b")
            if target == "configured":
                return os.environ.get("KITTY_MODEL", FREE_ROUTER_MODEL)
            return FREE_ROUTER_MODEL
        if normalized_mode == "max":
            return os.environ.get("KITTY_MAX_MODEL", "deepseek/deepseek-r1")
        return FREE_ROUTER_MODEL
