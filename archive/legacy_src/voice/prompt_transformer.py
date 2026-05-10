"""
Voice Prompt Transformer

Sits between KittyEars (raw Whisper transcript) and CoreOrchestrator.
Cleans transcription artifacts, infers intent, and returns a structured prompt.

Why this exists: raw voice transcription is messy — filler words, false starts,
leaked system prompts from other tools, garbled punctuation. This layer makes it
usable before it hits routing.
"""

import re
from dataclasses import dataclass


@dataclass
class TransformedPrompt:
    original: str
    cleaned: str
    domain_hint: str | None  # auto / audio / fitness / code / self — if detectable
    intent_type: str            # question / command / journal / unclear
    confidence: float           # 0.0–1.0


# Phrases that indicate a leaked system prompt or transcription artifact
_ARTIFACT_PATTERNS = [
    r"(?i)^(um+|uh+|hmm+|ah+)[,\s]*",
    r"(?i)\b(you know what i mean|like i said|anyways|i mean|right\?|you know)\b",
    r"(?i)(ignore that|sorry about that|that was a mistake|disregard)",
    # Common Whisper hallucinations at silence boundaries
    r"(?i)^(thanks for watching|subscribe|thank you)\b",
]

_DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "auto":    ["car", "truck", "ridgeline", "engine", "battery", "brake", "transmission", "oil", "dtc", "code p0", "rpm", "cylinder"],
    "audio":   ["speaker", "amplifier", "amp", "capacitor", "resistor", "solder", "audio", "wiring", "ohm", "receiver", "subwoofer"],
    "fitness": ["workout", "recovery", "training", "exercise", "sleep", "nutrition", "protein", "hrv", "rpe", "zone"],
    "code":    ["function", "bug", "python", "typescript", "api", "database", "deploy", "git", "error", "import"],
    "self":    ["feel", "feeling", "anxious", "stressed", "tired", "motivated", "goal", "journal", "morning", "mood"],
}


def _strip_artifacts(text: str) -> str:
    for pattern in _ARTIFACT_PATTERNS:
        text = re.sub(pattern, "", text)
    text = re.sub(r"\s{2,}", " ", text)
    # Clean up orphaned punctuation after stripping mid-sentence phrases
    text = re.sub(r",\s*([,?.!])", r"\1", text)
    text = re.sub(r"\s+([,?.!])", r"\1", text)
    text = text.strip().strip(",").strip()
    if text:
        text = text[0].upper() + text[1:]
    return text


def _detect_domain(text: str) -> str | None:
    lower = text.lower()
    scores: dict[str, int] = {}
    for domain, keywords in _DOMAIN_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in lower)
        if score:
            scores[domain] = score
    if not scores:
        return None
    return max(scores, key=lambda d: scores[d])


def _detect_intent(text: str) -> str:
    lower = text.lower().strip()
    if any(lower.startswith(w) for w in ("how", "what", "why", "when", "where", "who", "is ", "are ", "can ", "does ", "do ")):
        return "question"
    if any(lower.startswith(w) for w in ("add", "fix", "update", "create", "build", "write", "delete", "show", "run", "check", "find")):
        return "command"
    if any(w in lower for w in ("feel", "feeling", "today was", "morning", "journal", "i'm", "i am", "i've been")):
        return "journal"
    return "unclear"


def transform(raw_transcript: str) -> TransformedPrompt:
    """
    Clean a raw Whisper transcript into a structured prompt.

    Usage:
        from src.voice.prompt_transformer import transform
        result = transform(raw_text)
        # Pass result.cleaned to CoreOrchestrator, result.domain_hint to router
    """
    if not raw_transcript or not raw_transcript.strip():
        return TransformedPrompt(
            original=raw_transcript,
            cleaned="",
            domain_hint=None,
            intent_type="unclear",
            confidence=0.0,
        )

    cleaned = _strip_artifacts(raw_transcript.strip())
    domain = _detect_domain(cleaned)
    intent = _detect_intent(cleaned)

    # Rough confidence: penalize if cleaned is much shorter than original (lots stripped)
    ratio = len(cleaned) / max(len(raw_transcript), 1)
    confidence = min(1.0, ratio * 1.2)

    return TransformedPrompt(
        original=raw_transcript,
        cleaned=cleaned,
        domain_hint=domain,
        intent_type=intent,
        confidence=confidence,
    )
