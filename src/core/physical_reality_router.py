#!/usr/bin/env python3
"""
Physical Reality Router - Hardware Diagnostic Stop-and-Verify
Detects when queries cross from digital → physical world and triggers verification workflows.
Prevents hallucinated answers about physical hardware.
"""

import re
from dataclasses import dataclass
from enum import Enum


class RealityIntent(Enum):
    """Classification of query intent regarding physical reality."""

    DIGITAL = "DIGITAL"
    PHYSICAL_DIAGNOSTIC = "PHYSICAL_DIAGNOSTIC"
    MIXED = "MIXED"


class RealityAction(Enum):
    """Recommended action based on classification."""

    PROCEED = "PROCEED"
    HALT = "HALT"
    VERIFY = "VERIFY"


import json
from pathlib import Path

_CONFIG_PATH = Path(__file__).parent.parent.parent / "config" / "hardware_triggers.json"
with open(_CONFIG_PATH, "r") as f:
    HARDWARE_TRIGGER_WORDS = json.load(f)


@dataclass
class PhysicalRealityResult:
    """
    Structured result from physical reality classification.

    Attributes:
        intent: DIGITAL | PHYSICAL_DIAGNOSTIC | MIXED
        action: PROCEED | HALT | VERIFY
        response: User-facing message for HALT/VERIFY actions
        trigger_domains: Which hardware domains were detected
        matched_keywords: Specific keywords that triggered classification
        confidence: Confidence score for the classification (0.0-1.0)
        reasoning: Human-readable explanation of the classification
    """

    intent: RealityIntent
    action: RealityAction
    response: str
    trigger_domains: list[str]
    matched_keywords: list[str]
    confidence: float
    reasoning: str


class PhysicalRealityClassifier:
    """
    Classifier that detects when user queries involve physical reality
    and require sensory verification before diagnosis.

    This prevents LLM hallucinations about hardware - the AI cannot
    see, hear, smell, or touch physical systems, so it must ask for
    evidence before diagnosing.

    Usage:
        classifier = PhysicalRealityClassifier()
        result = classifier.classify("My amp is making a buzzing sound")
        if result.action == RealityAction.VERIFY:
            print(result.response)  # Ask user for sensory data
    """

    # Minimum number of keywords needed to trigger PHYSICAL_DIAGNOSTIC
    PHYSICAL_THRESHOLD = 1

    # Minimum number of keywords needed to trigger MIXED classification
    # when query also has strong digital context
    MIXED_THRESHOLD = 2

    def __init__(self):
        """Initialize the classifier with compiled patterns."""
        self._build_patterns()

    def _build_patterns(self) -> None:
        """Pre-compile regex patterns for efficient matching."""
        # Build flat list of all trigger words for quick iteration
        self._all_keywords: list[str] = []
        self._domain_keywords: dict[str, list[str]] = {}

        for domain, keywords in HARDWARE_TRIGGER_WORDS.items():
            self._domain_keywords[domain] = keywords
            self._all_keywords.extend(keywords)

        # Sort by length (longest first) to match multi-word phrases first
        self._all_keywords.sort(key=len, reverse=True)

        # Compile regex patterns (case-insensitive)
        self._patterns = [
            re.compile(r"\b" + re.escape(word) + r"\b", re.IGNORECASE)
            for word in self._all_keywords
        ]

    def classify(self, query: str) -> PhysicalRealityResult:
        """
        Classify a user query for physical reality content.

        Args:
            query: The user's input query

        Returns:
            PhysicalRealityResult with classification details and response
        """
        query_lower = query.lower()
        matched_domains: dict[str, list[str]] = {}
        all_matches: list[str] = []

        # Scan for keyword matches across all domains
        for domain, keywords in self._domain_keywords.items():
            domain_matches = []
            for keyword in keywords:
                if keyword.lower() in query_lower:
                    domain_matches.append(keyword)
                    if keyword not in all_matches:
                        all_matches.append(keyword)

            if domain_matches:
                matched_domains[domain] = domain_matches

        # Calculate classification
        total_matches = len(all_matches)

        if total_matches == 0:
            return self._digital_result()

        # Calculate confidence based on match density
        confidence = min(1.0, total_matches / 3.0)
        if confidence < 0.34 and total_matches > 0:
            confidence = 0.34

        # Determine intent based on match characteristics
        intent = self._determine_intent(matched_domains, query_lower)

        if intent == RealityIntent.PHYSICAL_DIAGNOSTIC:
            return self._physical_result(matched_domains, all_matches, confidence)
        elif intent == RealityIntent.MIXED:
            return self._mixed_result(matched_domains, all_matches, confidence)
        else:
            return self._digital_result()

    def _determine_intent(
        self, matched_domains: dict[str, list[str]], query_lower: str
    ) -> RealityIntent:
        """Determine the intent classification based on matched domains."""
        # High-priority sensory keywords that strongly indicate physical
        sensory_priority = [
            "smell",
            "smells",
            "sounds",
            "see",
            "look",
            "listen",
            "touch",
            "feel",
            "leak",
            "vibration",
            "buzzing",
            "hum",
            "noise",
            "smoke",
            "burning",
        ]

        # Check for sensory keywords
        has_sensory = any(
            any(kw in query_lower for kw in sensory_priority)
            for sensory_priority in [sensory_priority]
        )
        if has_sensory:
            for kw in sensory_priority:
                if kw in query_lower:
                    return RealityIntent.PHYSICAL_DIAGNOSTIC

        # Check domain distribution
        sum(len(matches) for matches in matched_domains.values())

        # Pure physical domains
        physical_domains = {
            "automotive",
            "audio_electronics",
            "sensory",
            "mechanical",
            "electrical",
            "plumbing",
            "hvac",
        }
        matched_physical = any(d in physical_domains for d in matched_domains)

        if matched_physical:
            return RealityIntent.PHYSICAL_DIAGNOSTIC

        return RealityIntent.PHYSICAL_DIAGNOSTIC  # Default to physical if any matches

    def _digital_result(self) -> PhysicalRealityResult:
        """Generate result for purely digital queries."""
        return PhysicalRealityResult(
            intent=RealityIntent.DIGITAL,
            action=RealityAction.PROCEED,
            response="",
            trigger_domains=[],
            matched_keywords=[],
            confidence=0.0,
            reasoning="No physical reality keywords detected",
        )

    def _physical_result(
        self, matched_domains: dict[str, list[str]], all_matches: list[str], confidence: float
    ) -> PhysicalRealityResult:
        """Generate result for physical diagnostic queries."""
        domains = list(matched_domains.keys())

        # Generate helpful response asking for sensory data
        response = self._generate_verification_prompt(matched_domains)

        reasoning = f"Detected physical domain keywords: {', '.join(all_matches[:5])}"
        if len(all_matches) > 5:
            reasoning += f" and {len(all_matches) - 5} more"

        return PhysicalRealityResult(
            intent=RealityIntent.PHYSICAL_DIAGNOSTIC,
            action=RealityAction.VERIFY,
            response=response,
            trigger_domains=domains,
            matched_keywords=all_matches,
            confidence=confidence,
            reasoning=reasoning,
        )

    def _mixed_result(
        self, matched_domains: dict[str, list[str]], all_matches: list[str], confidence: float
    ) -> PhysicalRealityResult:
        """Generate result for mixed digital/physical queries."""
        domains = list(matched_domains.keys())

        response = self._generate_verification_prompt(matched_domains)

        return PhysicalRealityResult(
            intent=RealityIntent.MIXED,
            action=RealityAction.VERIFY,
            response=response,
            trigger_domains=domains,
            matched_keywords=all_matches,
            confidence=confidence,
            reasoning=f"Mixed content detected with physical keywords: {', '.join(all_matches[:3])}",
        )

    def _generate_verification_prompt(self, matched_domains: dict[str, list[str]]) -> str:
        """Generate a helpful verification prompt based on detected domains."""
        # Primary domains and their specific prompts
        domain_prompts = {
            "sensory": "Before I diagnose this, I need some info. Could you describe the specific symptom? Or if you have a photo, that would help a lot.",
            "audio_electronics": "Before I diagnose that, I need some info. Could you describe the specific symptom (buzzing, hum, no sound)? Or paste a photo of the issue?",
            "automotive": "Before I diagnose that, I need some info. What symptoms are you seeing? Is there a check engine light, noise, or leak? A photo would help.",
            "mechanical": "Before I diagnose that, I need some info. Can you describe what's happening or what's broken? A photo would really help.",
            "electrical": "Before I diagnose that, I need some info. What symptoms are you seeing (no power, flickering, burning smell)? Safety first - any photos?",
            "plumbing": "Before I diagnose that, I need some info. Is there a leak, clog, or low pressure? Can you describe or photograph the issue?",
            "hvac": "Before I diagnose that, I need some info. Is it heating, cooling, or airflow issues? Any error codes or strange noises?",
        }

        # Determine primary domain
        primary_domain = self._get_primary_domain(matched_domains)

        # Return domain-specific prompt or generic fallback
        return domain_prompts.get(
            primary_domain,
            "Before I diagnose that, I need some info. Could you describe the specific symptom, or paste a photo?",
        )

    def _get_primary_domain(self, matched_domains: dict[str, list[str]]) -> str:
        """Determine the primary domain from matches (sensory keywords prioritized)."""
        # Sensory domain has highest priority
        if "sensory" in matched_domains:
            return "sensory"

        # Otherwise, return largest matched domain
        if matched_domains:
            return max(matched_domains.keys(), key=lambda d: len(matched_domains[d]))

        return "generic"


class PhysicalRealityRouter:
    """
    Main router class that integrates with DomainRouter for pre-checks.

    This class provides the complete integration interface for routing
    physical reality queries through the stop-and-verify workflow.

    Usage:
        router = PhysicalRealityRouter()

        # Pre-check before LLM diagnosis
        result = router.pre_check("My amp is making a strange noise")
        if result.action != RealityAction.PROCEED:
            return result.response

        # Proceed with normal diagnosis...
    """

    def __init__(self):
        self.classifier = PhysicalRealityClassifier()

    def pre_check(self, query: str) -> PhysicalRealityResult:
        """
        Run pre-check on query before allowing physical diagnosis.

        This should be called as a gate before any hardware-related
        LLM diagnosis to prevent hallucinations.

        Args:
            query: The user's input query

        Returns:
            PhysicalRealityResult with action and response
        """
        return self.classifier.classify(query)

    def should_verify(self, query: str) -> bool:
        """Quick check if query requires verification."""
        result = self.pre_check(query)
        return result.action in (RealityAction.HALT, RealityAction.VERIFY)

    def get_verification_response(self, query: str) -> str:
        """
        Get the verification prompt for a query.

        Returns empty string if no verification needed.
        """
        result = self.pre_check(query)
        return result.response

    def integrate_with_domain_router(
        self,
        domain_router_decision: "RoutingDecision",  # noqa: F821
        query: str,
    ) -> dict:
        """
        Integrate physical reality check with DomainRouter decision.

        This method combines DomainRouter's domain classification with
        the physical reality check for complete query analysis.

        Args:
            domain_router_decision: The RoutingDecision from DomainRouter
            query: The original user query

        Returns:
            Dict with combined routing information
        """
        reality_result = self.pre_check(query)

        return {
            "domain_decision": domain_router_decision,
            "reality_check": reality_result,
            "should_proceed": (
                reality_result.action == RealityAction.PROCEED
                or domain_router_decision.domain.value in ["code", "general"]
            ),
            "requires_verification": reality_result.action != RealityAction.PROCEED,
            "verification_response": reality_result.response,
            "metadata": {
                "intent": reality_result.intent.value,
                "confidence": reality_result.confidence,
                "trigger_domains": reality_result.trigger_domains,
                "matched_keywords": reality_result.matched_keywords,
            },
        }


# Convenience function for quick checks
def check_physical_reality(query: str) -> PhysicalRealityResult:
    """Quick function for checking if a query requires physical verification."""
    router = PhysicalRealityRouter()
    return router.pre_check(query)


# Test and demonstration
if __name__ == "__main__":
    print("=" * 80)
    print("PHYSICAL REALITY ROUTER - TEST")
    print("=" * 80)
    print()

    router = PhysicalRealityRouter()

    test_queries = [
        # Physical Reality Queries
        "My tube amp is making a buzzing sound and smells like it's overheating",
        "My Honda Ridgeline won't start, just clicks when I turn the key",
        "My speaker has a rattle when I play loud music",
        "There's a burning smell coming from under my car hood",
        "The brakes on my truck squeak when I stop",
        "My preamp is outputting a loud hum even with nothing connected",
        "Check engine light is on and it feels like it's misfiring",
        "Can you help me understand this schematic?",
        "The suspension on my motorcycle is making a knocking noise",
        "There's fluid leaking under my vehicle",
        # Digital Queries
        "Write Python code to parse JSON",
        "What is the capital of France?",
        "How do I center a div in CSS?",
        "Explain machine learning concepts",
        # Mixed Queries
        "I have a Python script that's connecting to an amplifier API",
        "My car's OBD2 scanner shows code P0301",
    ]

    print("QUERY ANALYSIS")
    print("-" * 80)

    for query in test_queries:
        result = router.pre_check(query)
        status_icon = {
            RealityAction.PROCEED: "✅",
            RealityAction.HALT: "🛑",
            RealityAction.VERIFY: "🔍",
        }.get(result.action, "?")

        print(f'\nQuery: "{query}"')
        print(f"  {status_icon} Intent: {result.intent.value}")
        print(f"  {status_icon} Action: {result.action.value}")
        print(f"  {status_icon} Confidence: {result.confidence:.0%}")

        if result.trigger_domains:
            print(f"  {status_icon} Domains: {', '.join(result.trigger_domains)}")

        if result.matched_keywords:
            print(f"  {status_icon} Keywords: {', '.join(result.matched_keywords[:3])}")

        if result.response:
            print(f"  💬 {result.response}")

    print()
    print("=" * 80)
    print("✅ Physical Reality Router ready!")
    print()
    print("Integration with DomainRouter:")
    print("  from src.core.physical_reality_router import PhysicalRealityRouter")
    print("  router = PhysicalRealityRouter()")
    print("  result = router.pre_check(user_query)")
    print("  if result.action != RealityAction.PROCEED:")
    print("      return result.response  # Ask for sensory data")
    print()
