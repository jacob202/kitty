import json
import logging
import os
from dataclasses import dataclass, field

try:
    from src.utils.performance_hooks import middleware_tracker

    _PERF_HOOKS_AVAILABLE = True
except ImportError:
    _PERF_HOOKS_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class MiddlewareResult:
    original_prompt: str
    enhanced_prompt: str
    intent: str
    route: str  # 'local', 'flash', 'heavy', 'council'
    model: str  # specific model name
    clarity_score: int
    needs_clarification: bool
    warnings: list[str] = field(default_factory=list)
    ui_state: str = "[STATE:CALM]"


class KittyMiddleware:
    """
    The "Amalgamated" Middleware: Prompt Enhancer + Cost Router.
    Routes tasks to Local (Llama/Qwen) vs Paid (Gemini/Claude) models.
    """

    SIMPLE_TRIGGERS = [
        "hi",
        "hello",
        "hey",
        "yo",
        "sup",
        "greetings",
        "how are you",
        "who are you",
        "what is your name",
        "status",
        "is ollama running",
        "help",
        "commands",
    ]

    ELECTRONICS_KEYWORDS = [
        "sansui",
        "schematic",
        "capacitor",
        "transistor",
        "resistor",
        "pcb",
        "solder",
        "multimeter",
        "oscilloscope",
        "repair",
        "bias",
        "offset",
        "protection relay",
        "power supply",
        "voltage",
    ]

    def __init__(self, config_path: str = "config/config.json"):
        self.config = self._load_config(config_path)
        self._openrouter_key = os.environ.get("OPENROUTER_API_KEY")

    def _load_config(self, path: str) -> dict:
        try:
            with open(path) as f:
                return json.load(f)
        except Exception:
            return {}

    def process(self, prompt: str, history: list[dict] = None) -> MiddlewareResult:
        """Main entry point: Enhance prompt and route to best cost/performance model."""

        # 1. Basic Cleaning
        clean_prompt = prompt.strip()
        low_prompt = clean_prompt.lower()

        # 2. Fast Path: Trivial Greetings / Status
        if any(low_prompt == t for t in self.SIMPLE_TRIGGERS) or len(low_prompt.split()) < 3:
            return MiddlewareResult(
                original_prompt=clean_prompt,
                enhanced_prompt=clean_prompt,
                intent="greeting",
                route="local",
                model=self.config.get("ollama_model", "llama3.2:3b"),
                clarity_score=10,
                needs_clarification=False,
                ui_state="[STATE:CALM]",
            )

        # 3. Intent Classification
        intent = self._classify_intent(low_prompt)

        # 4. Prompt Enhancement
        enhanced = self._enhance(clean_prompt, intent, low_prompt)

        # 5. Cost Routing Decision
        route, model, ui_state = self._route(low_prompt, intent)

        # 6. Clarity Check (Fallback style if no API, but we'll keep it simple)
        score, needs_clear, warnings = self._check_clarity(low_prompt)

        result = MiddlewareResult(
            original_prompt=clean_prompt,
            enhanced_prompt=enhanced,
            intent=intent,
            route=route,
            model=model,
            clarity_score=score,
            needs_clarification=needs_clear,
            warnings=warnings,
            ui_state=ui_state,
        )

        # Track routing decision for performance monitoring
        if _PERF_HOOKS_AVAILABLE:
            try:
                middleware_tracker.track_route(result)
            except Exception:
                pass  # Non-fatal

        return result

    def _classify_intent(self, prompt: str) -> str:
        if any(kw in prompt for kw in self.ELECTRONICS_KEYWORDS):
            return "electronics_repair"
        if any(kw in prompt for kw in ["write", "code", "build", "implement", "fix", "debug"]):
            return "coding"
        if any(kw in prompt for kw in ["find", "search", "research", "lookup"]):
            return "research"
        if any(kw in prompt for kw in ["explain", "how does", "what is"]):
            return "explanation"
        return "general"

    def _enhance(self, prompt: str, intent: str, low_prompt: str) -> str:
        """Structure messy input into a high-quality prompt."""
        header = f"[Task] {prompt}\n"
        context = "[Context]\n- System: Kitty AI (Electronics Repair Specialist)\n"

        if intent == "electronics_repair":
            context += "- Focus: Vintage Audio Repair (Sansui 9090/AU-717)\n"
            context += "- Tools: Schematic Analyzer, BOM Manager, Local RAG\n"
        elif intent == "coding":
            context += "- Focus: Production-grade Python/TypeScript\n"

        requirements = "[Requirements]\n"
        if intent == "coding":
            requirements += "- Include error handling and type hints\n- Modular structure\n"
        elif intent == "electronics_repair":
            requirements += "- Check safety/discharge first\n- Reference exact component designators (e.g., C05)\n"
        else:
            requirements += "- Be concise and accurate\n"

        return f"{header}\n{context}\n{requirements}\n[Output]\n- Structured response with actionable steps."

    def _route(self, prompt: str, intent: str) -> tuple[str, str, str]:
        """Determine if we can use a cheap local model or need the 'Big Brain'."""

        # Force Local for specific keywords
        if "local" in prompt or "ollama" in prompt:
            return "local", self.config.get("ollama_model", "llama3.2:3b"), "[STATE:CALM]"

        # Use Local for very simple questions
        if len(prompt.split()) < 10 and intent not in ["electronics_repair", "coding"]:
            return "local", self.config.get("ollama_model", "llama3.2:3b"), "[STATE:CALM]"

        # Use Flash (Gemini) for Electronics/Vision/General - Best Cost/Performance
        if intent == "electronics_repair" or intent == "explanation":
            return (
                "flash",
                self.config.get("flash_model", "google/gemini-2.0-flash-001"),
                "[STATE:HELPFUL]",
            )

        # Use Heavy (Claude/DeepSeek) for Coding/Complex Logic
        if intent == "coding" or intent == "research":
            return (
                "heavy",
                self.config.get("cheap_model", "deepseek/deepseek-chat"),
                "[STATE:FOCUS]",
            )

        # Default to Flash
        return (
            "flash",
            self.config.get("flash_model", "google/gemini-2.0-flash-001"),
            "[STATE:UNHINGED]",
        )

    def _check_clarity(self, prompt: str) -> tuple[int, bool, list[str]]:
        words = prompt.split()
        score = 10
        warnings = []

        if len(words) < 4:
            score -= 4
            warnings.append("Prompt is very short/vague")
        if any(w in prompt for w in ["it", "this", "stuff", "thing"]):
            score -= 2
            warnings.append("Contains ambiguous pronouns")

        return max(1, score), score < 7, warnings
