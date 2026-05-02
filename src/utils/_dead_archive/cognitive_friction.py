"""
Cognitive Friction Enforcer - Safety checkpoint before destructive or irreversible actions.

Problem: AI agents confidently execute bad commands that:
- Delete files without confirmation
- Overwrite important data
- Run destructive shell commands
- Make irreversible decisions based on guessed information

Solution: A "brakes" layer that evaluates proposed actions against:
1. Destructiveness (rm, mv, chmod, etc.)
2. Verifiability (does AI have CURRENT data, or is it guessing?)
3. Reversibility (can this be undone?)
4. Confidence level (is this a hallucination or verified fact?)

Decision Matrix:
- SAFE → proceed
- UNCERTAIN → halt, ask for clarification
- GUESSING → reject, search first
"""

import re
from dataclasses import dataclass
from enum import Enum


class ActionStatus(Enum):
    PROCEED = "proceed"
    HALT = "halt"
    REJECT = "reject"


@dataclass
class FrictionCheck:
    name: str
    passed: bool
    details: str


@dataclass
class FrictionDecision:
    status: ActionStatus
    reason: str
    checks: list[FrictionCheck]
    clarification_needed: str | None = None

    @property
    def is_safe(self) -> bool:
        return self.status == ActionStatus.PROCEED


class CognitiveFrictionEnforcer:
    """
    Acts as the final gatekeeper before Kitty executes terminal commands
    or modifies the file system.
    """

    # Destructive command patterns
    DANGEROUS_PATTERNS = [
        (r"\brm\s+-rf\b", "Recursive force delete - will destroy directories"),
        (r"\brm\s+/\b", "Delete root - catastrophic"),
        (r"\brm\s+-\s*[rf]\s+\$\{", "Shell expansion delete - unpredictable"),
        (r"\bsudo\s+rm\b", "Privileged delete - bypassing safety"),
        (r"\bdd\s+if\b.*of\s*=/dev/", "Direct disk write - extremely dangerous"),
        (r"\bmkfs\b", "Filesystem format - destructive"),
        (r"\bpartition\b", "Disk partition - dangerous"),
        (r"\bshred\b", "Secure delete - unrecoverable"),
        (r"\b>\s*/dev/sd", "Direct device write"),
        (r"\bchmod\s+777\b", "World-writable - security risk"),
        (r"\bchmod\s+-R\s+777\b", "Recursive 777 - security disaster"),
        (r"\bchown\s+-R\b", "Recursive ownership change"),
        (r"\bkill\s+-9\b", "Force kill - may cause data loss"),
        (r"\bpkill\s+-9\b", "Force process kill"),
        (r"\breboot\b", "Immediate reboot - unsaved data lost"),
        (r"\bshutdown\b", "System shutdown"),
        (r"\bdrop\s+database\b", "Database destruction"),
        (r"\bDROP\s+TABLE\b", "Table destruction"),
        (r"\bDELETE\s+FROM\b.*WHERE\s+1\s*=\s*1", "Unconditional delete - catastrophic"),
    ]

    # Commands that need verification
    MODIFYING_PATTERNS = [
        (r"\brm\b", "File deletion"),
        (r"\bmv\b", "File move/rename"),
        (r"\bcp\b.*\s+-f\b", "Force copy - overwrites"),
        (r"\bwget\b", "Network download - external code"),
        (r"\bcurl\b.*\s+-d\b", "HTTP POST - sends data"),
        (r"\bgit\s+push\s+--force\b", "Force push - rewrites history"),
        (r"\bgit\s+reset\s+--hard\b", "Hard reset - loses uncommitted changes"),
        (r"\bnpm\s+install\s+-g\b", "Global npm - affects system"),
        (r"\bsudo\s+apt\b", "System package install"),
        (r"\bsudo\s+yum\b", "System package install"),
        (r"\bbrew\s+install\b", "Homebrew install"),
        (r"\bdocker\s+rm\b", "Container deletion"),
        (r"\bdocker\s+rmi\b", "Image deletion"),
        (r"\bkubectl\s+delete\b", "Kubernetes resource deletion"),
    ]

    def __init__(self, require_confirmation_threshold: str = "medium"):
        """
        Initialize enforcer.

        Args:
            require_confirmation_threshold: "low", "medium", "high"
                - low: Only block obviously destructive
                - medium: Also block modifying commands
                - high: Block anything that could have side effects
        """
        self.threshold = require_confirmation_threshold

    def evaluate(
        self, intent: str, proposed_action: str, context: dict | None = None
    ) -> FrictionDecision:
        """
        Evaluate a proposed action against the friction checklist.

        Args:
            intent: The user's stated intent
            proposed_action: The command Kitty wants to execute
            context: Additional context (has_file_verified, has_searched, etc.)

        Returns:
            FrictionDecision with status and reason
        """
        checks = []
        context = context or {}

        # Check 1: Is it destructive?
        destructive_check = self._check_destructiveness(proposed_action)
        checks.append(destructive_check)

        # Check 2: Does Kitty have verified data?
        verifiable_check = self._check_verifiability(intent, proposed_action, context)
        checks.append(verifiable_check)

        # Check 3: Could this cause an infinite loop?
        loop_check = self._check_infinite_loop(proposed_action)
        checks.append(loop_check)

        # Check 4: Is it modifying system state?
        modifying_check = self._check_system_modification(proposed_action)
        checks.append(modifying_check)

        # Determine decision
        if not destructive_check.passed:
            return FrictionDecision(
                status=ActionStatus.REJECT,
                reason=f"DESTRUCTIVE: {destructive_check.details}",
                checks=checks,
                clarification_needed="This command would cause irreversible damage. Please confirm the exact target and purpose.",
            )

        if not verifiable_check.passed:
            return FrictionDecision(
                status=ActionStatus.HALT,
                reason=f"UNCERTAIN: {verifiable_check.details}",
                checks=checks,
                clarification_needed=verifiable_check.details,
            )

        if not loop_check.passed:
            return FrictionDecision(
                status=ActionStatus.REJECT,
                reason=f"RISK OF LOOP: {loop_check.details}",
                checks=checks,
                clarification_needed="This could create an infinite loop. Add a termination condition.",
            )

        if self.threshold in ("medium", "high") and not modifying_check.passed:
            return FrictionDecision(
                status=ActionStatus.HALT,
                reason=f"REQUIRES CONFIRMATION: {modifying_check.details}",
                checks=checks,
                clarification_needed="This will modify system state. Confirm you want to proceed.",
            )

        return FrictionDecision(
            status=ActionStatus.PROCEED,
            reason="All checks passed. Action verified and safe.",
            checks=checks,
        )

    def _check_destructiveness(self, action: str) -> FrictionCheck:
        """Check if action is obviously destructive."""
        for pattern, description in self.DANGEROUS_PATTERNS:
            if re.search(pattern, action, re.IGNORECASE):
                return FrictionCheck(
                    name="destructiveness",
                    passed=False,
                    details=description,
                )
        return FrictionCheck(
            name="destructiveness",
            passed=True,
            details="No destructive patterns detected",
        )

    def _check_verifiability(self, intent: str, action: str, context: dict) -> FrictionCheck:
        """
        Check if Kitty is guessing or has verified information.

        This is the key "Cognitive Friction" check - it prevents
        the AI from confidently hallucinating commands.
        """
        has_verified_data = context.get("has_file_verified", False)
        has_searched = context.get("has_searched", False)
        has_memory = context.get("has_memory_access", False)

        # Hallucination indicators in intent
        hallucination_patterns = [
            r"i think it\'s",
            r"probably",
            r"might be",
            r"should be around",
            r"try deleting.*maybe",
            r"just guessing",
            r"not sure but",
            r"something like",
        ]

        intent_is_guessy = any(re.search(p, intent, re.IGNORECASE) for p in hallucination_patterns)

        # Missing verification indicators
        has_verification = has_verified_data or has_searched or has_memory

        if intent_is_guessy and not has_verification:
            return FrictionCheck(
                name="verifiability",
                passed=False,
                details="Intent contains uncertainty markers but no verification performed. Kitty is guessing.",
            )

        if not has_verification and len(action) > 50:
            # Long command without any verification is risky
            return FrictionCheck(
                name="verifiability",
                passed=False,
                details="Complex command with no verification in memory. Confirm before proceeding.",
            )

        return FrictionCheck(
            name="verifiability",
            passed=True,
            details="Intent is clear or verification is available",
        )

    def _check_infinite_loop(self, action: str) -> FrictionCheck:
        """Check for potential infinite loops."""
        # Pattern: while/for without clear termination
        loop_patterns = [
            r"while\s+true",
            r"while\s+\(",
            r"for\s*\(\s*;\s*;\s*\)",
        ]

        # But has a break?
        has_break = "break" in action.lower()
        has_timeout = "timeout" in action.lower() or "limit" in action.lower()

        for pattern in loop_patterns:
            if re.search(pattern, action, re.IGNORECASE):
                if not (has_break or has_timeout):
                    return FrictionCheck(
                        name="infinite_loop",
                        passed=False,
                        details="Loop detected without termination condition",
                    )

        return FrictionCheck(
            name="infinite_loop",
            passed=True,
            details="No infinite loop detected",
        )

    def _check_system_modification(self, action: str) -> FrictionCheck:
        """Check if action modifies system state."""
        for pattern, description in self.MODIFYING_PATTERNS:
            if re.search(pattern, action, re.IGNORECASE):
                return FrictionCheck(
                    name="system_modification",
                    passed=False,
                    details=description,
                )
        return FrictionCheck(
            name="system_modification",
            passed=True,
            details="No system modification detected",
        )

    def format_decision(self, decision: FrictionDecision) -> str:
        """Format decision for display to user."""
        if decision.is_safe:
            return f"✅ {decision.reason}"

        lines = [f"⚠️ {decision.status.value.upper()}"]
        lines.append(decision.reason)

        if decision.clarification_needed:
            lines.append(f"\n💬 {decision.clarification_needed}")

        lines.append("\nChecks:")
        for check in decision.checks:
            icon = "✅" if check.passed else "❌"
            lines.append(f"  {icon} {check.name}: {check.details}")

        return "\n".join(lines)
