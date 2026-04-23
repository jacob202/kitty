"""
Emotive Mirror — Real-time emotional analysis and persona modulation for Kitty.

Analyzes user's emotional state from input and determines:
- Appropriate persona (mechanic, whisper, default)
- Response verbosity modulation
- Match Energy integration

Usage:
    mirror = EmotiveMirror()
    directive = mirror.analyze("fix this fucking shit!")
    response = mirror.modulate_response(long_response_text)
"""

import json
import random
import re
import threading
from collections import deque
from dataclasses import dataclass
from datetime import datetime, time
from pathlib import Path

from src.personalization.fingerprint import (
    LinguisticFingerprint,
    Mood,
    get_mood_preset,
)

# ============================================================================
# DATA MODELS
# ============================================================================


@dataclass(frozen=True)
class PersonaDirective:
    """The result of emotion analysis — how Kitty should respond."""

    persona: str  # "mechanic" | "whisper" | "default"
    verbosity: str  # "minimal" | "low" | "normal"
    tone: str  # "direct" | "calm" | "friendly"
    energy_match: str  # "amped_up" | "enthusiastic" | "calm" | "grounded"
    emotion_signal: str  # Primary detected emotion
    emotion_intensity: float  # 0.0 - 1.0
    triggers: tuple[str, ...]  # What triggered this analysis
    modulation_hint: str | None = None  # e.g., "Honey badger for frustration"

    def __str__(self) -> str:
        return (
            f"PersonaDirective(persona={self.persona}, "
            f"verbosity={self.verbosity}, tone={self.tone}, "
            f"energy={self.energy_match}, emotion={self.emotion_signal} "
            f"({self.emotion_intensity:.0%}))"
        )


@dataclass
class TypingEvent:
    """A single typing event for timing analysis."""

    timestamp: datetime
    input_length: int


# ============================================================================
# PERSONA CONFIGURATIONS
# ============================================================================

PERSONA_CONFIGS: dict[str, dict[str, str]] = {
    "mechanic": {
        "verbosity": "minimal",
        "tone": "direct",
    },
    "whisper": {
        "verbosity": "low",
        "tone": "calm",
    },
    "default": {
        "verbosity": "normal",
        "tone": "friendly",
    },
}

# Quiet hours: 10pm - 5am
QUIET_HOURS_START = time(22, 0)
QUIET_HOURS_END = time(5, 0)


# ============================================================================
# EMOTION PATTERNS
# ============================================================================

# Profanity detection patterns
PROFANITY_PATTERNS = [
    r"\bfuck(?:ing|ed|s|er|ing)?\b",
    r"\bshit(?:ting|ted|s)?\b",
    r"\bdamn(?:ed|ing)?\b",
    r"\bcunt\b",
    r"\bcock\b",
    r"\bdick\b",
    r"\bpiss\b",
    r"\bcrap\b",
    r"\bbastard\b",
]

# Urgency indicators (not necessarily anger)
URGENCY_PATTERNS = [
    r"^[^a-z]+$",  # All caps words
    r"!!!+",  # Multiple exclamation marks
    r"\?{3,}",  # Multiple question marks
    r"\bURGENT\b",
    r"\bASAP\b",
    r"\bNOW\b",
    r"\bEMERGENCY\b",
]

# Frustration signals (profanity + short = frustration)
FRUSTRATION_SIGNALS = [
    "fuck",
    "shit",
    "damn",
    "goddamn",
    "motherfucker",
    "wtf",
    "jesus christ",
    "are you serious",
    "unbelievable",
]

# Honey badger phrases (empathy for frustration)
HONEY_BADGER_PHRASES = [
    "I've been there.",
    "I feel you.",
    "Let's fix it.",
    "No judgment.",
    "On it.",
    "Getting right to it.",
    "Let's work through this.",
]

# Positive energy signals (only amplify these)
POSITIVE_PATTERNS = [
    r"\b(awesome|amazing|perfect|nice|great|love)\b",
    r"\b(can't wait|excited|pumped|stoked)\b",
    r"\b(hell yes|fuck yeah|yesss|lets go)\b",
    r"!{2,}",  # Multiple exclamation marks without caps
]


# ============================================================================
# EMOTIVE MIRROR
# ============================================================================


class EmotiveMirror:
    """
    Real-time emotional analysis and persona modulation.

    Tracks typing patterns and analyzes input to determine:
    - Best persona (mechanic, whisper, default)
    - Response verbosity
    - Match Energy level

    Thread-safe with internal locking.
    """

    # Aspirational Ceiling: NEVER mirror frustration
    FRUSTRATION_SIGNALS = [
        "fuck",
        "shit",
        "damn",
        "goddamn",
        "motherfucker",
        "wtf",
        "jesus christ",
        "are you serious",
        "unbelievable",
    ]

    def __init__(
        self,
        history_size: int = 50,
        short_input_threshold: int = 30,
        frustration_window_minutes: int = 30,
    ):
        """
        Initialize the Emotive Mirror.

        Args:
            history_size: Max typing events to track in deque
            short_input_threshold: Characters considered "short input"
            frustration_window_minutes: Time window for frustration tracking
        """
        self._lock = threading.RLock()
        self._typing_history: deque[TypingEvent] = deque(maxlen=history_size)
        self._short_threshold = short_input_threshold
        self._frustration_window = frustration_window_minutes * 60  # Convert to seconds

        # Compile regex patterns once
        self._profanity_re = re.compile("|".join(PROFANITY_PATTERNS), re.IGNORECASE)
        self._urgency_re = re.compile("|".join(URGENCY_PATTERNS), re.IGNORECASE)
        self._positive_re = re.compile("|".join(POSITIVE_PATTERNS), re.IGNORECASE)

        # State tracking
        self._recent_frustration: list[datetime] = []
        self._honey_badger_mode: bool = False

        # Load fingerprint from ~/.kitty/fingerprint.json if it exists
        self._fingerprint = self._load_fingerprint()
        self._active_mood: Mood | None = None

    def _load_fingerprint(self) -> LinguisticFingerprint | None:
        """Load fingerprint from ~/.kitty/fingerprint.json if it exists."""
        fingerprint_path = Path.home() / ".kitty" / "fingerprint.json"
        if fingerprint_path.exists():
            try:
                with open(fingerprint_path) as f:
                    data = json.load(f)
                return LinguisticFingerprint.from_dict(data)
            except (json.JSONDecodeError, KeyError):
                pass
        return None

    def set_mood(self, mood: Mood) -> None:
        """
        Set active mood from /mood command.

        Uses preset values for response modulation.
        """
        with self._lock:
            self._active_mood = mood

    def get_mood_preset_values(self) -> dict:
        """Get the current mood preset values for response modulation."""
        with self._lock:
            if self._active_mood:
                return get_mood_preset(self._active_mood)
            if self._fingerprint and self._fingerprint.response_length_preference:
                return {
                    "response_length_preference": self._fingerprint.response_length_preference,
                    "humor_style": self._fingerprint.humor_style,
                    "exclamation_frequency": self._fingerprint.exclamation_frequency,
                }
            return get_mood_preset(Mood.FOCUSED)

    # ========================================================================
    # PUBLIC API
    # ========================================================================

    def analyze(self, user_input: str) -> PersonaDirective:
        """
        Analyze user input and return persona directive.

        Detects:
        - Profanity (anger, frustration)
        - ALL CAPS (urgency, shouting)
        - Short input + profanity (frustration)
        - Time-based (quiet hours)

        Args:
            user_input: Raw user input string

        Returns:
            PersonaDirective with persona, verbosity, tone, and energy match
        """
        with self._lock:
            # Record typing event
            self._record_typing_event(user_input)

            # Analyze emotions
            emotion_signal, emotion_intensity, triggers = self._detect_emotions(user_input)

            # Check quiet hours
            is_quiet_hours = self._is_quiet_hours()

            # Determine persona
            persona, verbosity, tone = self._determine_persona(
                user_input, emotion_signal, emotion_intensity, is_quiet_hours
            )

            # Determine energy match (from Match Energy integration)
            energy_match = self._determine_energy_match(
                user_input, emotion_signal, emotion_intensity
            )

            # Check for honey badger moment
            modulation_hint = self._get_modulation_hint(
                emotion_signal, emotion_intensity, energy_match
            )

            return PersonaDirective(
                persona=persona,
                verbosity=verbosity,
                tone=tone,
                energy_match=energy_match,
                emotion_signal=emotion_signal,
                emotion_intensity=emotion_intensity,
                triggers=triggers,
                modulation_hint=modulation_hint,
            )

    def modulate_response(
        self,
        response: str,
        verbosity: str | None = None,
        tone: str | None = None,
    ) -> str:
        """
        Modulate response based on verbosity settings.

        Modulation rules:
        - minimal: Keep only first 3 essential lines
        - low: 50% shorter
        - normal: unchanged

        Args:
            response: The response text to modulate
            verbosity: Override verbosity level (uses directive if None)
            tone: Override tone (currently unused, for future expansion)

        Returns:
            Modulated response string
        """
        verbosity = verbosity or "normal"

        if verbosity == "minimal":
            return self._modulate_minimal(response)
        elif verbosity == "low":
            return self._modulate_low(response)
        else:
            return response  # normal = unchanged

    def record_frustration(self):
        """Record a frustration event (called when frustration is detected)."""
        with self._lock:
            self._recent_frustration.append(datetime.now())
            self._honey_badger_mode = True

            # Clean up old entries
            cutoff = datetime.now().timestamp() - self._frustration_window
            self._recent_frustration = [
                ts for ts in self._recent_frustration if ts.timestamp() > cutoff
            ]

    def get_honey_badger_phrase(self) -> str | None:
        """
        Get honey badger empathy phrase if in frustration mode.

        Returns:
            Empathy phrase or None if not in honey badger mode
        """
        with self._lock:
            if not self._honey_badger_mode:
                return None

            # Check if frustration window has expired
            if not self._recent_frustration:
                self._honey_badger_mode = False
                return None

            return HONEY_BADGER_PHRASES[0]  # Return first phrase

    def get_typing_stats(self) -> dict:
        """Get typing pattern statistics."""
        with self._lock:
            if len(self._typing_history) < 2:
                return {"sample_size": len(self._typing_history)}

            events = list(self._typing_history)
            intervals = []
            lengths = []

            for i in range(1, len(events)):
                delta = (events[i].timestamp - events[i - 1].timestamp).total_seconds()
                intervals.append(delta)
                lengths.append(events[i].input_length)

            return {
                "sample_size": len(events),
                "avg_interval_sec": sum(intervals) / len(intervals) if intervals else 0,
                "avg_input_length": sum(lengths) / len(lengths) if lengths else 0,
                "recent_frustration_count": len(self._recent_frustration),
                "honey_badger_active": self._honey_badger_mode,
            }

    def reset(self):
        """Reset mirror state."""
        with self._lock:
            self._typing_history.clear()
            self._recent_frustration.clear()
            self._honey_badger_mode = False

    # ========================================================================
    # INTERNAL ANALYSIS
    # ========================================================================

    def _record_typing_event(self, user_input: str):
        """Record a typing event with timestamp."""
        self._typing_history.append(
            TypingEvent(timestamp=datetime.now(), input_length=len(user_input))
        )

    def _detect_emotions(self, user_input: str) -> tuple[str, float, tuple[str, ...]]:
        """
        Detect emotions from user input.

        Returns:
            Tuple of (emotion_signal, intensity, triggers)
        """
        triggers: list[str] = []
        emotion_scores: dict[str, float] = {
            "angry": 0.0,
            "frustrated": 0.0,
            "urgent": 0.0,
            "positive": 0.0,
            "neutral": 0.0,
        }

        user_input.lower()
        text_stripped = user_input.strip()

        # Check for profanity
        profanity_matches = self._profanity_re.findall(user_input)
        if profanity_matches:
            triggers.append("profanity")
            emotion_scores["frustrated"] += 0.4 * len(profanity_matches)

            # Check for ALL CAPS (suggests shouting/anger)
            if text_stripped.isupper() and len(text_stripped) > 3:
                triggers.append("all_caps")
                emotion_scores["angry"] += 0.5

        # Check for urgency patterns
        urgency_matches = self._urgency_re.findall(user_input)
        if urgency_matches:
            triggers.append("urgency")
            # If also has negative emotion, it's angry urgency
            if emotion_scores["angry"] > 0:
                emotion_scores["angry"] += 0.3
            else:
                emotion_scores["urgent"] += 0.4

        # Short input + profanity = frustration
        is_short = len(text_stripped) < self._short_threshold
        if is_short and profanity_matches:
            triggers.append("short_profanity")
            emotion_scores["frustrated"] += 0.3

        # Check for positive energy (only amplify these)
        positive_matches = self._positive_re.findall(user_input)
        if positive_matches:
            triggers.append("positive_energy")
            emotion_scores["positive"] += 0.5 * len(positive_matches)

        # ALL CAPS without profanity might be excitement
        if text_stripped.isupper() and len(text_stripped) > 5 and not profanity_matches:
            triggers.append("caps_excitement")
            emotion_scores["positive"] += 0.3

        # Determine dominant emotion
        dominant_emotion = max(emotion_scores, key=emotion_scores.get)
        intensity = emotion_scores[dominant_emotion]

        # Cap intensity at 1.0
        intensity = min(1.0, intensity)

        # If no emotion detected, default to neutral
        if intensity < 0.1:
            dominant_emotion = "neutral"

        return dominant_emotion, intensity, tuple(triggers)

    def _is_quiet_hours(self) -> bool:
        """Check if current time is in quiet hours (10pm - 5am)."""
        now = datetime.now().time()

        # Handle overnight quiet hours (10pm - 5am)
        if QUIET_HOURS_START <= now or now < QUIET_HOURS_END:
            return True
        return False

    def _determine_persona(
        self,
        user_input: str,
        emotion_signal: str,
        emotion_intensity: float,
        is_quiet_hours: bool,
    ) -> tuple[str, str, str]:
        """
        Determine the appropriate persona based on emotion analysis.

        Returns:
            Tuple of (persona, verbosity, tone)
        """
        # Anger always gets mechanic persona (direct, minimal)
        if emotion_signal == "angry":
            return ("mechanic", "minimal", "direct")

        # Frustration gets mechanic + honey badger empathy
        if emotion_signal == "frustrated":
            return ("mechanic", "minimal", "direct")

        # Quiet hours = whisper
        if is_quiet_hours:
            return ("whisper", "low", "calm")

        # Urgency = mechanic (get to the point)
        if emotion_signal == "urgent":
            return ("mechanic", "minimal", "direct")

        # Positive energy = default (friendly, normal)
        if emotion_signal == "positive":
            return ("default", "normal", "friendly")

        # Neutral = default
        return ("default", "normal", "friendly")

    def _determine_energy_match(
        self,
        user_input: str,
        emotion_signal: str,
        emotion_intensity: float,
    ) -> str:
        """
        Determine Match Energy level (from Honcho integration).

        Rules:
        - Only amplify positive emotions
        - Honey badger for frustration ("grounded")
        - Never amplify anger

        Returns:
            Energy match string: "amped_up" | "enthusiastic" | "calm" | "grounded"
        """
        text_lower = user_input.lower()

        # Check for amped up signals
        amped_patterns = [
            r"\bfuck yeah\b",
            r"\bhell yeah\b",
            r"\byesss\b",
            r"\blet's go\b",
            r"\bcan't wait\b",
            r"\bpumped\b",
            r"\bstoked\b",
        ]
        if any(re.search(p, text_lower) for p in amped_patterns):
            return "amped_up"

        # Check for enthusiastic signals
        enthusiastic_patterns = [
            r"\bawesome\b",
            r"\bamazing\b",
            r"\bperfect\b",
            r"\bnice\b",
            r"\bgreat\b",
            r"\blove it\b",
            r"\bexcited\b",
        ]
        if any(re.search(p, text_lower) for p in enthusiastic_patterns):
            return "enthusiastic"

        # Frustration = grounded (honey badger mode)
        if emotion_signal == "frustrated":
            return "grounded"

        # Anger = grounded (never amplify)
        if emotion_signal == "angry":
            return "grounded"

        # Urgency = calm (solution-focused, not amped)
        if emotion_signal == "urgent":
            return "calm"

        return "calm"  # Default

    def _get_modulation_hint(
        self,
        emotion_signal: str,
        emotion_intensity: float,
        energy_match: str,
    ) -> str | None:
        """
        Get modulation hint based on emotion and energy.

        Args:
            emotion_signal: Detected emotion
            emotion_intensity: 0.0 - 1.0 intensity
            energy_match: Match Energy level

        Returns:
            Optional hint for response modulation
        """
        # Honey badger for frustration
        if emotion_signal == "frustrated" and emotion_intensity >= 0.5:
            self.record_frustration()
            return "Honey badger: empathy before solution"

        # Never amplify anger
        if emotion_signal == "angry":
            return "Neutralize: calm, solution-focused"

        # Positive amplification allowed
        if energy_match in ("amped_up", "enthusiastic"):
            return f"Match energy: {energy_match}"

        return None

    # ========================================================================
    # RESPONSE MODULATION
    # ========================================================================

    def _modulate_minimal(self, response: str) -> str:
        """
        Modulate to minimal verbosity.

        Keeps only the first 3 essential lines.
        """
        lines = response.split("\n")
        essential_lines = []

        for line in lines:
            stripped = line.strip()
            # Skip empty lines
            if not stripped:
                continue
            # Skip obvious filler
            if stripped.startswith("#") and len(stripped) < 50:
                continue  # Short headers are ok
            essential_lines.append(line)
            if len(essential_lines) >= 3:
                break

        result = "\n".join(essential_lines)

        # If we have a very short response, just return it
        if len(essential_lines) <= 2:
            return response

        return result

    def _modulate_low(self, response: str) -> str:
        """
        Modulate to low verbosity.

        Reduces response to approximately 50% length.
        """
        lines = response.split("\n")
        total_lines = len(lines)

        if total_lines <= 2:
            return response  # Already short enough

        # Keep first half of lines
        keep_count = max(1, total_lines // 2)
        essential_lines = lines[:keep_count]

        # Add an ellipsis indicator if we cut content
        if keep_count < total_lines:
            # Find last meaningful line
            last_idx = len(essential_lines) - 1
            while last_idx > 0 and not essential_lines[last_idx].strip():
                last_idx -= 1
            # Add continuation marker
            essential_lines[last_idx] = essential_lines[last_idx].rstrip() + "..."

        return "\n".join(essential_lines)

    def modulate_by_fingerprint(
        self,
        response: str,
        emotion_signal: str = "neutral",
    ) -> str:
        """
        Modulate response based on user's linguistic fingerprint.

        Aspirational Ceiling: NEVER mirror frustration. If input is frustrated,
        output is calm/focused regardless of fingerprint.

        Modulation rules:
        - response_length_preference == "terse": Shorten response
        - exclamation_frequency > 0.1: Add exclamation on success
        - 2% chance: Inject signature phrase if available

        Args:
            response: The response text to modulate
            emotion_signal: Detected emotion (for aspirational ceiling check)

        Returns:
            Fingerprint-modulated response string
        """
        # Aspirational Ceiling: Never mirror frustration
        if emotion_signal == "frustrated":
            # Force calm/focused modulation regardless of fingerprint
            return self._modulate_by_aspirational_ceiling(response)

        # Get fingerprint or mood preset values
        preset = self.get_mood_preset_values()
        length_pref = preset.get("response_length_preference", "medium")
        exclamation_freq = preset.get("exclamation_frequency", 0.0)

        result = response

        # Shorten if terse preference
        if length_pref == "terse":
            result = self._modulate_minimal(result)

        # Add exclamation if frequency > 0.1 (success context)
        if exclamation_freq > 0.1 and not result.endswith("?"):
            # Only add on positive/confident responses
            positive_indicators = ["done", "fixed", "ready", "complete", "success", "working"]
            if any(ind in result.lower() for ind in positive_indicators):
                if not result.endswith("!"):
                    result = result.rstrip() + "!"

        # 2% chance to inject signature phrase
        if self._fingerprint and self._fingerprint.signature_phrases:
            if random.random() < 0.02:
                phrase = random.choice(self._fingerprint.signature_phrases)
                result = f"{result} {phrase}"

        return result

    def _modulate_by_aspirational_ceiling(self, response: str) -> str:
        """
        Force calm/focused response when user is frustrated.

        Aspirational Ceiling: Never mirror frustration.
        """
        # Use minimal/terse modulation
        result = self._modulate_minimal(response)

        # Ensure calm tone - strip any aggressive elements
        result = result.replace("!!", ".")
        result = result.replace("!?", ".")

        return result


# ============================================================================
# SINGLETON INSTANCE
# ============================================================================

_mirror_instance: EmotiveMirror | None = None
_mirror_lock = threading.Lock()


def get_emotive_mirror() -> EmotiveMirror:
    """
    Get singleton EmotiveMirror instance.

    Thread-safe singleton pattern.
    """
    global _mirror_instance
    if _mirror_instance is None:
        with _mirror_lock:
            if _mirror_instance is None:
                _mirror_instance = EmotiveMirror()
    return _mirror_instance


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================


def quick_analyze(user_input: str) -> PersonaDirective:
    """
    Quick analyze a single input string.

    Uses global singleton instance.
    """
    mirror = get_emotive_mirror()
    return mirror.analyze(user_input)


def quick_modulate(response: str, verbosity: str = "normal") -> str:
    """
    Quick modulate a response string.

    Uses global singleton instance.
    """
    mirror = get_emotive_mirror()
    return mirror.modulate_response(response, verbosity=verbosity)
