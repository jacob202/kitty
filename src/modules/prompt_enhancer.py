#!/usr/bin/env python3
"""
Prompt Enhancer - Transforms messy input into structured prompts
"""

import re
from datetime import datetime


class PromptEnhancer:
    """
    Middleware that transforms rambling user input into comprehensive prompts
    """

    def __init__(self, ollama_client=None):
        self.ollama = ollama_client
        self.user_patterns = self._load_patterns()

    def enhance(self, user_input: str, context: dict = None) -> str:
        """
        Main entry point - transform messy input into structured prompt
        """
        # Check if already clear (bypass enhancement)
        if self._is_already_clear(user_input):
            return user_input

        # Analyze intent
        intent = self._analyze_intent(user_input)

        # Enrich with context
        enriched = self._enrich_context(user_input, intent, context)

        # Build comprehensive prompt
        enhanced = self._construct_prompt(enriched, intent)

        return enhanced

    def _is_already_clear(self, text: str) -> bool:
        """Check if input is already well-structured"""
        # Clear prompts usually have:
        # - Specific questions
        # - Context provided
        # - Structured format

        indicators = [
            r"^how do i",
            r"^what is",
            r"^can you",
            r"^help me",
            r"^explain",
        ]

        text_lower = text.lower().strip()

        # If it's short and direct, it's probably clear
        if len(text) < 50 and any(re.match(pattern, text_lower) for pattern in indicators):
            return True

        # If it has structure (bullets, numbers), it's clear
        if re.search(r"^[\d\-\*]", text, re.MULTILINE):
            return True

        return False

    def _analyze_intent(self, text: str) -> dict:
        """Determine what the user wants"""
        text_lower = text.lower()

        # Electronics repair patterns
        if any(
            word in text_lower
            for word in ["amp", "amplifier", "guitar", "buzz", "noise", "fix", "repair", "broken"]
        ):
            return {
                "category": "electronics_repair",
                "confidence": 0.9,
                "subtype": "audio_equipment",
            }

        # Schematic analysis
        if any(
            word in text_lower
            for word in ["schematic", "circuit", "diagram", "component", "resistor", "capacitor"]
        ):
            return {
                "category": "schematic_analysis",
                "confidence": 0.9,
                "subtype": "circuit_analysis",
            }

        # Learning/explanation
        if any(
            word in text_lower
            for word in ["explain", "how does", "what is", "teach me", "understand"]
        ):
            return {"category": "learning", "confidence": 0.8, "subtype": "explanation"}

        # Component lookup
        if any(
            word in text_lower
            for word in ["part number", "datasheet", "specs", "replacement", "equivalent"]
        ):
            return {"category": "component_lookup", "confidence": 0.85, "subtype": "part_search"}

        # General/catch-all
        return {"category": "general", "confidence": 0.5, "subtype": "unknown"}

    def _enrich_context(self, text: str, intent: dict, context: dict = None) -> dict:
        """Pull relevant context from memory"""
        enriched = {
            "original": text,
            "intent": intent,
            "context": context or {},
            "user_preferences": self._get_user_preferences(),
            "similar_interactions": [],
        }

        # Add domain-specific context based on intent
        if intent["category"] == "electronics_repair":
            enriched["domain_context"] = {
                "common_issues": ["power_supply", "ground_loop", "component_failure"],
                "safety_notes": ["discharge_caps", "unplug_power"],
                "tools_needed": ["multimeter", "scope", "soldering_iron"],
            }

        elif intent["category"] == "schematic_analysis":
            enriched["domain_context"] = {
                "analysis_types": ["signal_flow", "power_rails", "component_id"],
                "output_formats": ["text", "visual", "interactive"],
            }

        return enriched

    def _construct_prompt(self, enriched: dict, intent: dict) -> str:
        """Build comprehensive prompt from enriched data"""

        original = enriched["original"]
        category = intent["category"]

        # Build role-specific prompt
        if category == "electronics_repair":
            return f"""ROLE: Electronics repair expert specializing in audio equipment
EXPERTISE: Advanced troubleshooting, component-level repair, safety procedures

USER QUERY: {original}

CONTEXT:
- This appears to be an electronics repair question
- User may be working on audio equipment (amp/guitar)
- Safety is paramount - emphasize discharge procedures

APPROACH:
1. Assess the symptoms described
2. Identify most likely failure points
3. Provide step-by-step diagnostic procedure
4. Include safety warnings where appropriate
5. Suggest specific components to check
6. Offer replacement recommendations if needed

OUTPUT FORMAT:
- Start with safety warning if applicable
- Provide clear, numbered steps
- Include specific component references
- Suggest tools needed for each step
- End with "Did this help?" to continue the conversation

TONE: Helpful, technical but accessible, safety-conscious"""

        elif category == "schematic_analysis":
            return f"""ROLE: Circuit analysis expert with deep knowledge of analog electronics
EXPERTISE: Schematic interpretation, signal flow analysis, component identification

USER QUERY: {original}

CONTEXT:
- User is asking about circuit/schematic analysis
- May need help identifying components, tracing signals, or understanding function
- Visual/spatial reasoning important

APPROACH:
1. Identify what specific analysis is needed
2. Break down circuit into functional blocks
3. Explain signal path or component function
4. Use analogies where helpful
5. Suggest test points or measurements if applicable

OUTPUT FORMAT:
- Identify circuit type first (power supply, amplifier, etc.)
- Explain function in plain terms
- Use visual descriptions ("imagine current flowing from...")
- Highlight key components and their roles
- Offer to trace specific signals if requested

TONE: Educational, visual, patient"""

        elif category == "learning":
            return f"""ROLE: Electronics educator specializing in making complex concepts accessible
EXPERTISE: Analog electronics, practical applications, hands-on learning

USER QUERY: {original}

CONTEXT:
- User wants to learn/understand a concept
- Beginner to intermediate level (based on query style)
- Practical application important

APPROACH:
1. Start with the "why" - why does this matter?
2. Use analogies to everyday experiences
3. Build from simple to complex
4. Include practical examples
5. Offer resources for deeper learning

OUTPUT FORMAT:
- Simple analogy first
- Technical explanation second
- Practical example third
- Common misconceptions to avoid
- "Try this" - hands-on suggestion

TONE: Encouraging, patient, analogy-rich"""

        else:
            # General enhancement
            return f"""ROLE: Helpful technical assistant

USER QUERY: {original}

CONTEXT:
- User has a technical question
- Provide clear, actionable response
- Ask clarifying questions if needed

OUTPUT FORMAT:
- Direct answer to the question
- Supporting details
- Next steps or follow-up questions

TONE: Helpful, concise, professional"""

    def _get_user_preferences(self) -> dict:
        """Load learned user preferences"""
        # In real implementation, load from ChromaDB or file
        return {
            "communication_style": "step_by_step",
            "prefers_visuals": True,
            "technical_level": "intermediate",
            "common_topics": ["guitar_amps", "audio_electronics"],
        }

    def _load_patterns(self) -> dict:
        """Load successful interaction patterns"""
        return {}

    def record_feedback(self, original: str, enhanced: str, result_quality: int):
        """Record feedback to improve future enhancements"""
        # Store for learning
        {
            "timestamp": datetime.now().isoformat(),
            "original": original,
            "enhanced": enhanced,
            "quality": result_quality,
            "worked_well": result_quality >= 8,
        }

        # In real implementation, save to vector DB
        print(f"📊 Recorded feedback: quality={result_quality}/10")


# Quick test
if __name__ == "__main__":
    enhancer = PromptEnhancer()

    # Test cases
    test_inputs = [
        "hey can you help me fix this amp? it's making a buzzing noise and i think maybe the capacitors but not sure...",
        "what is a capacitor",
        "Explain how transistors work like I'm 5",
        "TDA2030 datasheet specs",
    ]

    print("=" * 60)
    print("PROMPT ENHANCER TEST")
    print("=" * 60)

    for inp in test_inputs:
        print(f"\n📝 INPUT: {inp[:60]}...")

        if enhancer._is_already_clear(inp):
            print("   ✓ Already clear - no enhancement needed")
            enhanced = inp
        else:
            enhanced = enhancer.enhance(inp)
            print(f"\n🎯 ENHANCED:\n{enhanced[:300]}...")

        print("-" * 60)
