"""
Enhanced Prompt Refiner v2.0 - The "In-Between" Layer
Takes simple/free-form input and builds comprehensive prompts for best results

Features:
- Builds detailed prompts from simple instructions
- Learns from chat history for context
- Shows refinement indicator
- Allow disable for next question
- Proactive prompt enhancement
"""

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


class Intent:
    CODE_WRITE = "code_write"
    CODE_EDIT = "code_edit"
    CODE_DEBUG = "code_debug"
    CODE_REVIEW = "code_review"
    RESEARCH = "research"
    EXPLAIN = "explain"
    BRAINSTORM = "brainstorm"
    QUESTION = "question"
    CREATE_AGENT = "create_agent"
    CONFIGURE = "configure"
    GENERAL = "general"


@dataclass
class RefinedPrompt:
    original: str
    enhanced: str
    intent: str
    agent: str
    tier: int
    refinement_count: int = 0
    history_context: list[str] = field(default_factory=list)
    was_refined: bool = False


class ChatHistory:
    """Load and search chat history for context"""

    def __init__(self):
        self.history: list[dict] = []
        self._load_history()

    def _load_history(self):
        """Load available chat history"""
        history_files = [
            ".aider.chat.history.md",
            "data/chat_history.json",
            "data/chat_history.jsonl",
            "data/logs/canonical_log.jsonl",
            "data/vector_store/memory.json",
            "data/vector_store/session.json",
            "data/core_memory.json",
        ]

        for path in history_files:
            if Path(path).exists():
                try:
                    with open(path) as f:
                        content = f.read()
                        # Parse useful context
                        self._extract_context(content)
                except Exception:
                    pass

    def _extract_context(self, content: str):
        """Extract context from history"""
        # Simple extraction - look for user messages
        lines = content.split("\n")
        for line in lines[:100]:  # First 100 lines
            if len(line) > 20 and len(line) < 200:
                self.history.append({"text": line[:100], "timestamp": datetime.now().isoformat()})

    def search(self, query: str, limit: int = 3) -> list[str]:
        """Search history for related context"""
        query_lower = query.lower()
        results = []

        for item in self.history:
            # Simple keyword matching
            if any(word in item["text"].lower() for word in query_lower.split()[:3]):
                results.append(item["text"])
                if len(results) >= limit:
                    break

        return results

    def get_recent(self, limit: int = 5) -> list[str]:
        """Get recent conversation topics"""
        return [item["text"] for item in self.history[:limit]]


class EnhancedPromptRefiner:
    """Enhanced refiner - builds comprehensive prompts from simple input"""

    # Prompt templates for each intent
    TEMPLATES = {
        "code_write": {
            "context": "Write complete, production-ready code.",
            "requirements": [
                "Include proper error handling",
                "Add type hints where applicable",
                "Include docstrings",
                "Make it modular and reusable",
            ],
            "output": "Provide the complete code file.",
        },
        "code_edit": {
            "context": "Edit existing code with precision.",
            "requirements": [
                "Make minimal necessary changes",
                "Preserve existing functionality",
                "Explain what changed and why",
                "Check for side effects",
            ],
            "output": "Show the changed code with explanation.",
        },
        "code_debug": {
            "context": "Debug and fix the issue thoroughly.",
            "requirements": [
                "Identify root cause, not just symptoms",
                "Provide complete fix with explanation",
                "Suggest prevention strategies",
                "Check for similar issues elsewhere",
            ],
            "output": "Explain the bug and provide working fix.",
        },
        "code_review": {
            "context": "Review code for quality and improvements.",
            "requirements": [
                "Check for bugs and security issues",
                "Suggest performance improvements",
                "Note code style consistency",
                "Provide specific actionable feedback",
            ],
            "output": "Detailed review with prioritized suggestions.",
        },
        "research": {
            "context": "Research thoroughly with sources.",
            "requirements": [
                "Provide comprehensive information",
                "Include multiple sources/approaches",
                "Compare pros and cons",
                "Give practical examples",
            ],
            "output": "Well-researched answer with references.",
        },
        "explain": {
            "context": "Explain clearly with depth.",
            "requirements": [
                "Start with clear summary",
                "Use analogies where helpful",
                "Provide code examples",
                "Anticipate follow-up questions",
            ],
            "output": "Clear explanation with examples.",
        },
        "brainstorm": {
            "context": "Brainstorm creative solutions.",
            "requirements": [
                "Provide multiple approaches",
                "For each: pros, cons, complexity",
                "Consider unconventional ideas",
                "Recommend best option with rationale",
            ],
            "output": "Diverse ideas with analysis.",
        },
        "create_agent": {
            "context": "Create a custom agent configuration.",
            "requirements": [
                "Define agent purpose and expertise",
                "List available tools",
                "Specify system prompt behavior",
                "Set appropriate model and parameters",
            ],
            "output": "Complete agent specification.",
        },
        "general": {
            "context": "Be helpful, thorough, and proactive.",
            "requirements": [
                "Provide complete answer",
                "Ask clarifying questions if needed",
                "Anticipate related needs",
                "Offer to elaborate",
            ],
            "output": "Comprehensive response.",
        },
    }

    # Cost control keywords
    COST_KEYWORDS = {
        "tier1": ["cheap", "budget", "fast", "quick", "simple", "tier 1"],
        "tier2": ["standard", "normal", "default", "tier 2"],
        "tier3": ["quality", "better", "thorough", "tier 3"],
        "tier4": ["best", "premium", "detailed", "tier 4"],
        "tier5": ["perfect", "comprehensive", "production", "tier 5"],
        "secret": ["secret", "unrestricted", "local", "offline", "matrix"],
    }

    def __init__(self, enable_refinement: bool = True):
        self.enable_refinement = enable_refinement
        self.history = ChatHistory()
        self._refinement_count = 0

    def disable_for_next(self):
        """Disable refinement for the next query"""
        self.enable_refinement = False

    def enable_after_next(self):
        """Re-enable refinement after next query"""
        self.enable_refinement = True

    def was_refined(self) -> bool:
        """Check if last prompt was refined"""
        return self._refinement_count > 0

    def get_indicator(self) -> str:
        """Get indicator string for UI"""
        if self._refinement_count > 0:
            return f"✨ Refined {self._refinement_count}×"
        return ""

    def classify_intent(self, text: str) -> str:
        """Classify user intent"""
        text_lower = text.lower()

        patterns = {
            "code_write": [
                r"^write\s+",
                r"^create\s+",
                r"^build\s+",
                r"^implement\s+",
                r"^make\s+a",
            ],
            "code_edit": [
                r"^fix\s+",
                r"^edit\s+",
                r"^update\s+",
                r"^modify\s+",
                r"^change\s+",
                r"^refactor",
            ],
            "code_debug": [
                r"debug",
                r"error",
                r"bug",
                r"not working",
                r"failed",
                r"crash",
            ],
            "code_review": [
                r"review",
                r"check",
                r"audit",
                r"improve\s+code",
                r"optimize",
            ],
            "research": [
                r"research",
                r"find",
                r"search",
                r"how\s+to",
                r"what\s+is",
                r"look\s+up",
            ],
            "explain": [
                r"explain",
                r"how\s+does",
                r"what\s+does",
                r"understand",
                r"learn\s+about",
            ],
            "brainstorm": [
                r"brainstorm",
                r"ideas",
                r"suggest",
                r"think\s+of",
                r"ways\s+to",
            ],
            "create_agent": [
                r"create\s+agent",
                r"add\s+specialist",
                r"new\s+agent",
                r"configure\s+agent",
            ],
            "configure": [
                r"configure",
                r"set\s+up",
                r"setup",
                r"enable",
                r"change\s+config",
            ],
        }

        for intent, regexes in patterns.items():
            for regex in regexes:
                if re.search(regex, text_lower):
                    return intent

        return "general"

    def extract_context(self, text: str) -> dict[str, str]:
        """Extract technical context from prompt"""
        context = {}

        # Language detection
        languages = [
            "python",
            "javascript",
            "typescript",
            "rust",
            "go",
            "java",
            "c++",
            "html",
            "css",
            "sql",
            "bash",
            "shell",
        ]
        for lang in languages:
            if lang in text.lower():
                context["language"] = lang
                break

        # Framework detection
        frameworks = [
            "react",
            "vue",
            "angular",
            "django",
            "flask",
            "fastapi",
            "nextjs",
            "express",
            "node",
        ]
        for fw in frameworks:
            if fw in text.lower():
                context["framework"] = fw
                break

        # File path detection
        file_match = re.search(r"([\w/-]+\.\w+)", text)
        if file_match:
            context["file"] = file_match.group(1)

        # Line reference
        line_match = re.search(r"line\s+(\d+)", text.lower())
        if line_match:
            context["line"] = line_match.group(1)

        # Error extraction
        if "error" in text.lower():
            error_match = re.search(r"error[:\s]+([^\n]+)", text, re.IGNORECASE)
            if error_match:
                context["error"] = error_match.group(1)[:100]

        return context

    def determine_tier(self, text: str) -> tuple[str, int]:
        """Determine cost tier and agent"""
        text_lower = text.lower()

        # Check for secret mode
        for kw in self.COST_KEYWORDS["secret"]:
            if kw in text_lower:
                return "ollama/qwen2.5-coder:7b", 1

        # Check for explicit tier
        for tier, keywords in self.COST_KEYWORDS.items():
            for kw in keywords:
                if kw in text_lower:
                    tier_num = int(tier.replace("tier", ""))
                    agents = {
                        1: "deepseek-chat",
                        2: "deepseek-chat",
                        3: "claude-sonnet",
                        4: "claude-opus",
                        5: "claude-opus",
                    }
                    return agents.get(tier_num, "auto"), tier_num

        return "auto", 2  # Default

    def build_comprehensive_prompt(
        self, text: str, intent: str, context: dict, history_context: list[str]
    ) -> str:
        """Build a comprehensive prompt from simple input"""

        # Get template
        template = self.TEMPLATES.get(intent, self.TEMPLATES["general"])

        # Start with enhanced context
        enhanced = f"[Task] {text}\n\n"

        # Add context section
        if context:
            enhanced += "[Context]\n"
            if "language" in context:
                enhanced += f"- Language: {context['language']}\n"
            if "framework" in context:
                enhanced += f"- Framework: {context['framework']}\n"
            if "file" in context:
                enhanced += f"- Target file: {context['file']}\n"
            if "line" in context:
                enhanced += f"- Relevant line: {context['line']}\n"
            if "error" in context:
                enhanced += f"- Error: {context['error']}\n"
            enhanced += "\n"

        # Add history context if relevant
        if history_context:
            enhanced += "[Recent Context]\n"
            for ctx in history_context[:2]:
                if ctx.lower() != text.lower():
                    enhanced += f"- Related: {ctx}\n"
            enhanced += "\n"

        # Add requirements
        enhanced += "[Requirements]\n"
        for req in template["requirements"]:
            enhanced += f"- {req}\n"
        enhanced += "\n"

        # Add output format
        enhanced += f"[Output Format]\n- {template['output']}\n"

        return enhanced

    def refine(self, text: str) -> RefinedPrompt:
        """Main entry point - refine simple input to comprehensive prompt"""

        if not self.enable_refinement:
            return RefinedPrompt(
                original=text,
                enhanced=text,
                intent="general",
                agent="auto",
                tier=2,
                was_refined=False,
            )

        # 1. Classify intent
        intent = self.classify_intent(text)

        # 2. Extract technical context
        context = self.extract_context(text)

        # 3. Search history for context
        history_context = self.history.search(text)

        # 4. Determine tier
        agent, tier = self.determine_tier(text)

        # 5. Build comprehensive prompt
        enhanced = self.build_comprehensive_prompt(text, intent, context, history_context)

        # Track refinement
        was_refined = enhanced != text
        if was_refined:
            self._refinement_count += 1

        return RefinedPrompt(
            original=text,
            enhanced=enhanced,
            intent=intent,
            agent=agent,
            tier=tier,
            refinement_count=self._refinement_count,
            history_context=history_context,
            was_refined=was_refined,
        )


def demo():
    """Demo the enhanced refiner"""
    refiner = EnhancedPromptRefiner()

    test_inputs = [
        "fix the error in main.py",
        "write python API",
        "make it faster",
        "explain how async works",
        "help me create an agent",
    ]

    print("=" * 60)
    print("ENHANCED PROMPT REFINER v2.0")
    print("=" * 60)

    for inp in test_inputs:
        result = refiner.refine(inp)

        print(f"\n📝 INPUT: {inp}")
        print(f"   Intent: {result.intent} | Agent: {result.agent} | Tier: {result.tier}")
        print(f"   Refined: {result.was_refined}")

        if result.was_refined:
            print("   📝 ENHANCED:")
            for line in result.enhanced.split("\n")[:15]:
                print(f"      {line}")

        # Check indicator
        indicator = refiner.get_indicator()
        if indicator:
            print(f"   {indicator}")


if __name__ == "__main__":
    demo()
