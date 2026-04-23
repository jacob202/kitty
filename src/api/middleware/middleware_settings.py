#!/usr/bin/env python3
"""
Settings-Aware Middleware for Kitty AI
Integrates profile settings with request routing and processing.
"""

import logging
from dataclasses import dataclass, field
from typing import Any

from src.config.settings_manager import SettingsManager, settings_manager

logger = logging.getLogger(__name__)


@dataclass
class RoutingDecision:
    """Result of a routing decision."""

    route: str  # 'local', 'flash', 'heavy', 'council'
    model: str  # specific model name
    reason: str  # why this route was chosen
    estimated_cost: float
    use_tools: list[str] = field(default_factory=list)


class SettingsAwareMiddleware:
    """
    Middleware that uses profile settings to make intelligent routing decisions.
    Extends the base KittyMiddleware with profile-aware routing.
    """

    def __init__(self, settings_mgr: SettingsManager | None = None):
        """
        Initialize the settings-aware middleware.

        Args:
            settings_mgr: SettingsManager instance. Uses global if not provided.
        """
        self.settings_mgr = settings_mgr or settings_manager
        self.profile = self.settings_mgr.get_active_profile()

    def reload_profile(self):
        """Reload the active profile (call after profile switch)."""
        self.profile = self.settings_mgr.get_active_profile()
        logger.info(f"Reloaded profile: {self.profile.name}")

    def process_with_settings(self, prompt: str, context: dict | None = None) -> dict[str, Any]:
        """
        Process a prompt using the active profile settings.

        Args:
            prompt: User input prompt
            context: Optional context information

        Returns:
            Dict with enhanced prompt, routing decision, and settings
        """
        context = context or {}

        # Get profile settings
        profile = self.profile

        # Apply system prompt prefix based on profile
        enhanced_prompt = self._enhance_prompt(prompt, profile)

        # Make routing decision based on middleware settings
        routing = self._determine_route(prompt, profile)

        # Determine which tools to enable
        available_tools = self._get_available_tools(profile)

        return {
            "original_prompt": prompt,
            "enhanced_prompt": enhanced_prompt,
            "system_prompt": profile.system_prompt,
            "routing": routing,
            "model_config": {
                "provider": profile.model.provider,
                "model_name": profile.model.model_name,
                "temperature": profile.model.temperature,
                "max_tokens": profile.model.max_tokens,
                "top_p": profile.model.top_p,
                "frequency_penalty": profile.model.frequency_penalty,
                "presence_penalty": profile.model.presence_penalty,
            },
            "available_tools": available_tools,
            "thinking_style": profile.thinking_style,
            "response_format": profile.response_format,
            "personality": profile.personality,
        }

    def _enhance_prompt(self, prompt: str, profile) -> str:
        """Enhance the prompt based on profile settings."""
        enhancements = []

        # Add thinking style directive
        if profile.thinking_style == "step-by-step":
            enhancements.append("Think through this step-by-step.")
        elif profile.thinking_style == "creative":
            enhancements.append("Be creative and explore multiple approaches.")
        elif profile.thinking_style == "direct":
            enhancements.append("Provide a direct, concise answer.")

        # Add response format directive
        if profile.response_format == "concise":
            enhancements.append("Keep your response brief and to the point.")
        elif profile.response_format == "structured":
            enhancements.append("Structure your response with clear sections.")
        elif profile.response_format == "verbose":
            enhancements.append("Provide a comprehensive, detailed response.")

        # Combine with original prompt
        if enhancements:
            return f"{' '.join(enhancements)}\n\n{prompt}"
        return prompt

    def _determine_route(self, prompt: str, profile) -> RoutingDecision:
        """
        Determine the best routing based on profile middleware settings.

        Args:
            prompt: User prompt
            profile: Active profile settings

        Returns:
            RoutingDecision with route details
        """
        mw = profile.middleware

        # If auto-routing is disabled, use profile's default model
        if not mw.auto_route:
            return RoutingDecision(
                route="direct",
                model=profile.model.model_name,
                reason="Auto-routing disabled - using profile default",
                estimated_cost=0.05,
                use_tools=self._get_relevant_tools(prompt, profile),
            )

        # Analyze prompt for routing hints
        prompt_lower = prompt.lower()
        is_simple = len(prompt.split()) < 10
        is_coding = any(
            kw in prompt_lower
            for kw in [
                "code",
                "program",
                "function",
                "class",
                "debug",
                "error",
                "implement",
                "write",
                "script",
                "python",
                "javascript",
            ]
        )
        is_vision = any(
            kw in prompt_lower
            for kw in [
                "image",
                "picture",
                "photo",
                "diagram",
                "schematic",
                "pcb",
                "board",
                "component",
                "look at",
                "analyze this",
            ]
        )
        is_research = any(
            kw in prompt_lower
            for kw in [
                "research",
                "find",
                "search",
                "lookup",
                "information about",
                "what is",
                "how does",
                "explain",
            ]
        )

        # Route based on settings and content
        if is_simple and mw.prefer_local_for_simple:
            return RoutingDecision(
                route="local",
                model="llama3.2:3b",
                reason="Simple query - using local model",
                estimated_cost=0.0,
                use_tools=[],
            )

        if is_vision and mw.prefer_flash_for_vision:
            return RoutingDecision(
                route="flash",
                model="google/gemini-2.0-flash-001",
                reason="Vision task - using flash model",
                estimated_cost=0.005,
                use_tools=["vision_analysis"],
            )

        if is_coding and mw.prefer_heavy_for_coding:
            return RoutingDecision(
                route="heavy",
                model="claude-3-5-sonnet",
                reason="Coding task - using heavy model",
                estimated_cost=0.03,
                use_tools=["code_execution"],
            )

        if is_research:
            return RoutingDecision(
                route="flash",
                model="google/gemini-2.0-flash-001",
                reason="Research task - using flash model",
                estimated_cost=0.01,
                use_tools=["web_search", "vector_search"],
            )

        # Default to profile's configured model
        route_map = {"claude": "heavy", "openai": "flash", "ollama": "local"}

        return RoutingDecision(
            route=route_map.get(profile.model.provider, "flash"),
            model=profile.model.model_name,
            reason="Using profile default model",
            estimated_cost=0.02,
            use_tools=self._get_relevant_tools(prompt, profile),
        )

    def _get_available_tools(self, profile) -> list[str]:
        """Get list of available tools based on profile settings."""
        tools = profile.tools
        available = []

        if tools.web_search:
            available.append("web_search")
        if tools.code_execution:
            available.append("code_execution")
        if tools.file_operations:
            available.append("file_operations")
        if tools.schematic_analysis:
            available.append("schematic_analysis")
        if tools.bom_manager:
            available.append("bom_manager")
        if tools.datasheet_lookup:
            available.append("datasheet_lookup")
        if tools.vision_analysis:
            available.append("vision_analysis")
        if tools.vector_search:
            available.append("vector_search")
        if tools.memory_recall:
            available.append("memory_recall")
        if tools.custom_agents:
            available.append("custom_agents")

        return available

    def _get_relevant_tools(self, prompt: str, profile) -> list[str]:
        """Determine which tools are relevant for this prompt."""
        prompt_lower = prompt.lower()
        tools = profile.tools
        relevant = []

        # Check for tool-relevant keywords
        if tools.web_search and any(
            kw in prompt_lower for kw in ["search", "find", "look up", "research", "information"]
        ):
            relevant.append("web_search")

        if tools.code_execution and any(
            kw in prompt_lower for kw in ["code", "run", "execute", "test", "debug"]
        ):
            relevant.append("code_execution")

        if tools.schematic_analysis and any(
            kw in prompt_lower for kw in ["schematic", "circuit", "pcb", "board", "diagram"]
        ):
            relevant.append("schematic_analysis")

        if tools.bom_manager and any(
            kw in prompt_lower for kw in ["bom", "bill of materials", "parts list", "components"]
        ):
            relevant.append("bom_manager")

        if tools.datasheet_lookup and any(
            kw in prompt_lower for kw in ["datasheet", "spec", "specification", "pdf"]
        ):
            relevant.append("datasheet_lookup")

        if tools.vision_analysis and any(
            kw in prompt_lower for kw in ["image", "photo", "picture", "look at", "analyze this"]
        ):
            relevant.append("vision_analysis")

        # Always include memory if enabled
        if tools.memory_recall:
            relevant.append("memory_recall")

        return relevant

    def check_cost_threshold(self, estimated_cost: float) -> tuple[bool, str]:
        """
        Check if a request exceeds the cost threshold.

        Args:
            estimated_cost: Estimated cost of the request

        Returns:
            Tuple of (allowed: bool, reason: str)
        """
        max_cost = self.profile.middleware.max_cost_per_request

        if estimated_cost > max_cost:
            return (
                False,
                f"Estimated cost (${estimated_cost:.4f}) exceeds threshold (${max_cost:.4f})",
            )

        return True, "Within cost threshold"

    def get_profile_info(self) -> dict[str, Any]:
        """Get current profile information."""
        return {
            "name": self.profile.name,
            "description": self.profile.description,
            "model": {
                "provider": self.profile.model.provider,
                "model_name": self.profile.model.model_name,
            },
            "personality": self.profile.personality,
            "tools_enabled": len(self._get_available_tools(self.profile)),
            "middleware": {
                "auto_route": self.profile.middleware.auto_route,
                "max_cost_per_request": self.profile.middleware.max_cost_per_request,
            },
        }


# Global instance
middleware = SettingsAwareMiddleware()


def get_middleware() -> SettingsAwareMiddleware:
    """Get the global middleware instance."""
    return middleware


def reload_middleware_profile():
    """Reload the middleware profile (call after switching profiles)."""
    middleware.reload_profile()


if __name__ == "__main__":
    # Test the middleware
    mw = SettingsAwareMiddleware()

    print("Profile Info:")
    info = mw.get_profile_info()
    for key, value in info.items():
        print(f"  {key}: {value}")

    print("\nTest prompts:")
    test_prompts = [
        "Hi there!",
        "Debug this Python error",
        "Analyze this schematic",
        "Research quantum computing",
        "Look at this image and tell me what you see",
    ]

    for prompt in test_prompts:
        print(f"\nPrompt: {prompt}")
        result = mw.process_with_settings(prompt)
        routing = result["routing"]
        print(f"  Route: {routing.route}")
        print(f"  Model: {routing.model}")
        print(f"  Reason: {routing.reason}")
        print(f"  Tools: {routing.use_tools}")
