"""
Chaos Injector - Red-team testing framework for Kitty's resilience.

Problem: You don't know what breaks until it breaks in production.
- API timeouts during complex operations
- Context window overflows
- Tool execution failures
- Network partitions
- Ollama crashes on M1 Mac

Solution: Chaos Monkey that randomly injects failures to verify:
1. Tiered fallback logic works (Local → Cloud → Premium)
2. Error messages are human-readable
3. Recovery is graceful, not catastrophic

Usage:
    chaos = ChaosInjector()
    scenario = chaos.generate_scenario("api_timeout")
    result = chaos.run_scenario(scenario, kitty_callback)
"""

import random
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class ChaosType(Enum):
    MODEL_TIMEOUT = "model_timeout"
    CONTEXT_OVERFLOW = "context_overflow"
    TOOL_FAILURE = "tool_failure"
    NETWORK_PARTITION = "network_partition"
    RATE_LIMIT = "rate_limit"
    AUTH_FAILURE = "auth_failure"
    PARTIAL_RESPONSE = "partial_response"
    SLOW_RESPONSE = "slow_response"


@dataclass
class ChaosScenario:
    id: str
    chaos_type: ChaosType
    description: str
    injection_point: str  # Where to inject (api, context, tool, etc.)
    trigger_delay: float  # Seconds before injection
    expected_behavior: str  # How Kitty SHOULD handle this
    severity: str  # critical, high, medium, low


@dataclass
class ChaosResult:
    scenario_id: str
    chaos_type: ChaosType
    passed: bool
    kitty_response: str
    fallback_triggered: bool
    recovery_graceful: bool
    error_message_user_facing: str
    internal_error_logged: str
    timestamp: str


class ChaosInjector:
    """
    Generates and runs chaos scenarios to stress-test Kitty's resilience.

    Categories:
    - API Failures (timeout, rate limit, auth)
    - Context Failures (overflow, truncation)
    - Tool Failures (permission denied, not found)
    - Network Failures (partition, latency)
    """

    SCENARIOS = {
        ChaosType.MODEL_TIMEOUT: [
            ChaosScenario(
                id="timeout_deepseek_midstream",
                chaos_type=ChaosType.MODEL_TIMEOUT,
                description="DeepSeek stops responding after generating 50 tokens",
                injection_point="api.deepseek.com",
                trigger_delay=2.0,
                expected_behavior="Silently catch timeout, switch to Claude via OpenRouter, append note to user",
                severity="high",
            ),
            ChaosScenario(
                id="timeout_ollama_m1",
                chaos_type=ChaosType.MODEL_TIMEOUT,
                description="Ollama on M1 Mac crashes with 'connection refused'",
                injection_point="localhost:11434",
                trigger_delay=0.5,
                expected_behavior="Fallback to Anthropic API with warning message",
                severity="medium",
            ),
        ],
        ChaosType.CONTEXT_OVERFLOW: [
            ChaosScenario(
                id="overflow_prompt_128k",
                chaos_type=ChaosType.CONTEXT_OVERFLOW,
                description="User prompt suddenly becomes 128k tokens",
                injection_point="context_manager",
                trigger_delay=0.1,
                expected_behavior="Truncate gracefully, summarize context, continue with reduced scope",
                severity="critical",
            ),
            ChaosScenario(
                id="overflow_conversation_history",
                chaos_type=ChaosType.CONTEXT_OVERFLOW,
                description="Conversation history exceeds context window",
                injection_point="conversation_manager",
                trigger_delay=1.0,
                expected_behavior="Summarize older messages, preserve recent context",
                severity="high",
            ),
        ],
        ChaosType.TOOL_FAILURE: [
            ChaosScenario(
                id="tool_bash_permission_denied",
                chaos_type=ChaosType.TOOL_FAILURE,
                description="Bash tool throws 'Permission Denied' when writing file",
                injection_point="bash_tool",
                trigger_delay=0.5,
                expected_behavior="Report permission issue, suggest fix, do NOT crash",
                severity="high",
            ),
            ChaosScenario(
                id="tool_file_not_found",
                chaos_type=ChaosType.TOOL_FAILURE,
                description="Read tool can't find referenced file",
                injection_point="read_tool",
                trigger_delay=0.3,
                expected_behavior="Report file missing, offer alternatives",
                severity="medium",
            ),
            ChaosScenario(
                id="tool_git_conflict",
                chaos_type=ChaosType.TOOL_FAILURE,
                description="Git operation fails due to merge conflict",
                injection_point="git_tool",
                trigger_delay=1.0,
                expected_behavior="Report conflict, show diff, guide resolution",
                severity="medium",
            ),
        ],
        ChaosType.NETWORK_PARTITION: [
            ChaosScenario(
                id="network_openrouter_down",
                chaos_type=ChaosType.NETWORK_PARTITION,
                description="OpenRouter becomes unreachable",
                injection_point="network",
                trigger_delay=2.0,
                expected_behavior="Fallback to Anthropic direct, warn about cost",
                severity="high",
            ),
        ],
        ChaosType.RATE_LIMIT: [
            ChaosScenario(
                id="rate_limit_anthropic",
                chaos_type=ChaosType.RATE_LIMIT,
                description="Anthropic returns 429 Too Many Requests",
                injection_point="api.anthropic.com",
                trigger_delay=1.0,
                expected_behavior="Respect rate limit, switch to local model, notify user",
                severity="medium",
            ),
        ],
        ChaosType.AUTH_FAILURE: [
            ChaosScenario(
                id="auth_openrouter_invalid",
                chaos_type=ChaosType.AUTH_FAILURE,
                description="OpenRouter returns 401 'User not found'",
                injection_point="api.openrouter.ai",
                trigger_delay=0.5,
                expected_behavior="Report auth issue, remove OpenRouter from fallback chain",
                severity="high",
            ),
        ],
        ChaosType.PARTIAL_RESPONSE: [
            ChaosScenario(
                id="partial_stream_cutoff",
                chaos_type=ChaosType.PARTIAL_RESPONSE,
                description="LLM stream cuts off mid-sentence",
                injection_point="stream_handler",
                trigger_delay=3.0,
                expected_behavior="Complete response naturally or indicate truncation",
                severity="medium",
            ),
        ],
        ChaosType.SLOW_RESPONSE: [
            ChaosScenario(
                id="slow_ollama_30s",
                chaos_type=ChaosType.SLOW_RESPONSE,
                description="Ollama takes 30+ seconds to respond",
                injection_point="localhost:11434",
                trigger_delay=5.0,
                expected_behavior="Show progress indicator, offer cancel option",
                severity="low",
            ),
        ],
    }

    def __init__(self, seed: int | None = None):
        """Initialize with optional random seed for reproducibility."""
        if seed:
            random.seed(seed)

    def get_scenario(self, chaos_type: ChaosType) -> ChaosScenario:
        """Get a random scenario of a specific type."""
        scenarios = self.SCENARIOS.get(chaos_type, [])
        if scenarios:
            return random.choice(scenarios)
        raise ValueError(f"No scenarios for type: {chaos_type}")

    def get_random_scenario(self, severity_filter: list[str] | None = None) -> ChaosScenario:
        """Get a random scenario, optionally filtered by severity."""
        all_scenarios = []
        for scenarios in self.SCENARIOS.values():
            if severity_filter:
                all_scenarios.extend(s for s in scenarios if s.severity in severity_filter)
            else:
                all_scenarios.extend(scenarios)

        return random.choice(all_scenarios)

    def generate_report(self, results: list[ChaosResult]) -> str:
        """Generate a chaos test report."""
        total = len(results)
        passed = sum(1 for r in results if r.passed)
        failed = total - passed

        lines = [
            "=" * 60,
            "CHAOS INJECTION TEST REPORT",
            "=" * 60,
            f"Timestamp: {datetime.now().isoformat()}",
            f"Total Scenarios: {total}",
            f"Passed: {passed} ({100 * passed / total:.0f}%)" if total > 0 else "Passed: 0",
            f"Failed: {failed}",
            "",
            "FAILURES:",
            "-" * 40,
        ]

        for r in results:
            if not r.passed:
                lines.append(f"\nScenario: {r.scenario_id}")
                lines.append(f"  Type: {r.chaos_type.value}")
                lines.append(f"  Kitty Response: {r.kitty_response[:100]}...")
                lines.append(f"  Fallback Triggered: {r.fallback_triggered}")
                lines.append(f"  Recovery Graceful: {r.recovery_graceful}")

        lines.extend(
            [
                "",
                "PASSES:",
                "-" * 40,
            ]
        )

        for r in results:
            if r.passed:
                lines.append(f"✅ {r.scenario_id} ({r.chaos_type.value})")

        lines.append("=" * 60)
        return "\n".join(lines)


class ChaosTestRunner:
    """
    Runs chaos scenarios against Kitty and evaluates resilience.
    """

    def __init__(self, chaos_injector: ChaosInjector):
        self.injector = chaos_injector

    def run_scenario(
        self, scenario: ChaosScenario, kitty_callback: Callable[[str], dict]
    ) -> ChaosResult:
        """
        Run a single chaos scenario.

        Args:
            scenario: The chaos scenario to inject
            kitty_callback: Function that takes user input, returns Kitty response

        Returns:
            ChaosResult with pass/fail evaluation
        """
        # In real implementation, this would:
        # 1. Set up mocks/fixtures for the chaos injection
        # 2. Run Kitty with the scenario
        # 3. Evaluate the response

        # For now, return a mock result structure
        return ChaosResult(
            scenario_id=scenario.id,
            chaos_type=scenario.chaos_type,
            passed=False,  # Would be evaluated
            kitty_response="",
            fallback_triggered=False,
            recovery_graceful=False,
            error_message_user_facing="",
            internal_error_logged="",
            timestamp=datetime.now().isoformat(),
        )

    def run_full_suite(self, severity_filter: list[str] | None = None) -> list[ChaosResult]:
        """Run all chaos scenarios."""
        results = []
        for chaos_type in ChaosType:
            try:
                scenario = self.injector.get_scenario(chaos_type)
                result = self.run_scenario(scenario, lambda x: {})
                results.append(result)
            except ValueError:
                pass  # No scenarios for this type
        return results


# CLI entry point
if __name__ == "__main__":
    chaos = ChaosInjector(seed=42)

    print("=== CHAOS INJECTOR ===\n")
    print("Available chaos types:")
    for ct in ChaosType:
        scenarios = chaos.SCENARIOS.get(ct, [])
        print(f"  {ct.value}: {len(scenarios)} scenarios")

    print("\nRandom scenario:")
    scenario = chaos.get_random_scenario()
    print(f"  ID: {scenario.id}")
    print(f"  Type: {scenario.chaos_type.value}")
    print(f"  Severity: {scenario.severity}")
    print(f"  Expected: {scenario.expected_behavior}")
