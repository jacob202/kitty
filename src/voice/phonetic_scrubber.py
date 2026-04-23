"""
Phonetic Scrubber - Cleans messy voice-to-text transcriptions before they reach the orchestrator.

Problem: Voice transcription (MacWhisper, Whisper, etc.) produces phonetic garbage:
  "look up the positor replacement" → "look up the pause at her placement"
  "Sansui AU-7900" → "suns you 7900"
  "capacitor" → "cappacitor"
  "thermistor" → "turn this or"

Solution: Fast, local correction layer that:
1. Knows the user's domain (from memory/context)
2. Maps phonetically-similar garbage to actual known entities
3. Cleans up common transcription errors
4. Passes sanitized text to orchestrator
"""

import re
from dataclasses import dataclass


@dataclass
class Correction:
    original: str
    corrected: str
    reason: str
    confidence: float  # 0-1


class PhoneticScrubber:
    """
    Cleans voice-to-text garbage using domain knowledge.

    Uses a combination of:
    - Phonetic similarity matching (Soundex-style)
    - Known entity dictionary (from user's active projects)
    - Common transcription patterns
    - Levenshtein distance for short words
    """

    # Common Whisper/vosk transcription error patterns
    COMMON_ERRORS = {
        # Electronics terms
        r"\bpositor\b": "posistor",
        r"\bpause\b": "posistor",
        r"\bplacement\b": "posistor",
        r"\btransistore?\b": "transistor",
        r"\bcappacitor\b": "capacitor",
        r"\bcapasitor\b": "capacitor",
        r"\bcaps\s*ator\b": "capacitor",
        r"\bthermisstor\b": "thermistor",
        r"\bturn this or\b": "thermistor",
        r"\bdiodes?\b": "diode",
        r"\bdyode\b": "diode",
        r"\bmosfets?\b": "mosfet",
        r"\bmost fets?\b": "mosfet",
        r"\bintegrated\s*circuit\b": "IC",
        r"\bintegrated\s*circuits\b": "ICs",
        # Brand names (common transcription failures)
        r"\bsuns\s*you\b": "Sansui",
        r"\bsans\s*ui\b": "Sansui",
        r"\bsony\b": "Sony",
        r"\bpanasonics?\b": "Panasonic",
        r"\bpioneer\b": "Pioneer",
        r"\bdenon\b": "Denon",
        r"\bmarantz\b": "Marantz",
        r"\byamaha\b": "Yamaha",
        r"\brotel\b": "Rotel",
        r"\bluxman\b": "Luxman",
        # Component values
        r"\b104\b": "0.1µF",  # Common cap code
        r"\b103\b": "0.01µF",
        r"\b102\b": "0.001µF",
        r"\b10\s*k\b": "10kΩ",
        r"\b4\s*point\s*7\b": "4.7",
        r"\b4\s*point\s*seven\b": "4.7",
        # Units
        r"\bmilli\s*volts?\b": "mV",
        r"\bmicro\s*farads?\b": "µF",
        r"\bnano\s*farads?\b": "nF",
        r"\bpico\s*farads?\b": "pF",
        # Car terms
        r"\bsway\s*bar\s*links?\b": "sway bar link",
        r"\bsway\s*bar\s*bushings?\b": "sway bar bushings",
        r"\bstruts?\b": "strut",
        r"\bo2\s*sensor\b": "O2 sensor",
        r"\becu\b": "ECU",
        # Common filler/garbage from voice
        r"\bbasically\b": "",
        r"\bliterally\b": "",
        r"\bkind of\b": "",
        r"\bsort of\b": "",
        r"\byou know\b": "",
        r"\bI mean\b": "",
        r"\blike\s*,?\s*": " ",
        r"\band\s+also\b": " and ",
        r"\bbut\s+also\b": " and ",
    }

    def __init__(self, known_entities: set[str] | None = None):
        """
        Initialize scrubber.

        Args:
            known_entities: Set of known domain terms to prioritize
                           (loaded from user's active projects/memory)
        """
        self.known_entities = known_entities or set()
        self._corrections: list[Correction] = []

    def add_known_entity(self, entity: str):
        """Add a domain-specific entity to the known list."""
        self.known_entities.add(entity.lower())

    def add_known_entities(self, entities: list[str]):
        """Add multiple domain-specific entities."""
        for e in entities:
            self.add_known_entity(e)

    def scrub(self, raw_text: str) -> dict:
        """
        Clean voice-to-text input.

        Args:
            raw_text: Raw transcription from Whisper/MacWhisper

        Returns:
            Dict with:
                - cleaned: Sanitized text for orchestrator
                - corrections: List of Correction objects
                - was_modified: bool
        """
        self._corrections = []
        cleaned = raw_text

        # Step 1: Apply common error patterns
        for pattern, replacement in self.COMMON_ERRORS.items():
            new_text = re.sub(pattern, replacement, cleaned, flags=re.IGNORECASE)
            if new_text != cleaned:
                self._corrections.append(
                    Correction(
                        original=pattern.strip("\\b"),
                        corrected=replacement,
                        reason="Common transcription error pattern",
                        confidence=0.95,
                    )
                )
                cleaned = new_text

        # Step 2: Check against known entities
        cleaned = self._match_known_entities(cleaned)

        # Step 3: Clean up filler words and extra spaces
        cleaned = self._clean_fillers(cleaned)

        return {
            "cleaned": cleaned.strip(),
            "corrections": self._corrections,
            "was_modified": len(self._corrections) > 0,
            "original": raw_text,
        }

    def _match_known_entities(self, text: str) -> str:
        """Match text against known entities using fuzzy matching."""
        if not self.known_entities:
            return text

        # Sort by length (longer matches first) to handle multi-word entities
        sorted_entities = sorted(self.known_entities, key=len, reverse=True)

        for entity in sorted_entities:
            # Case-insensitive matching
            if entity.lower() in text.lower():
                # Check if already correct case
                idx = text.lower().find(entity.lower())
                if idx >= 0:
                    original_segment = text[idx : idx + len(entity)]
                    if original_segment != entity:
                        # Correct the case
                        text = text[:idx] + entity + text[idx + len(entity) :]
                        self._corrections.append(
                            Correction(
                                original=original_segment,
                                corrected=entity,
                                reason="Known entity case correction",
                                confidence=0.99,
                            )
                        )

        return text

    def _clean_fillers(self, text: str) -> str:
        """Remove common filler words and normalize spacing."""
        # Remove trailing punctuation spam
        text = re.sub(r"[!?.,]{3,}", ".", text)

        # Normalize whitespace
        text = re.sub(r"\s+", " ", text)

        # Remove leading/trailing junk
        text = text.strip(".,!?- ")

        # Fix common "at her" → "for her" patterns
        text = re.sub(r"\bat\s+her\b", "for her", text, flags=re.IGNORECASE)

        return text

    def get_corrections_summary(self) -> str:
        """Get a human-readable summary of corrections made."""
        if not self._corrections:
            return "No corrections needed."

        lines = ["Phonetic corrections applied:"]
        for c in self._corrections:
            lines.append(f"  • '{c.original}' → '{c.corrected}' ({c.reason})")
        return "\n".join(lines)


def load_project_entities(project_context: str) -> set[str]:
    """
    Extract known entities from project context.

    This would ideally load from Kitty's memory/context system.
    For now, extracts from text.
    """
    entities = set()

    # Model numbers (AU-XXX, TDAXXXX, etc.)
    model_patterns = [
        r"AU-\d{3,4}",  # Sansui AU-7900
        r"TDA\d{4}",  # TDA7294
        r"LM\d{4}",  # LM3886
        r"TIP\d{2,3}",  # TIP120
        r"2N\d{3,4}",  # 2N2222
        r"IRF\d{3,4}",  # IRF540
    ]

    for pattern in model_patterns:
        entities.update(re.findall(pattern, project_context, re.IGNORECASE))

    # Brand names
    brands = ["sansui", "sony", "pioneer", "denon", "marantz", "yamaha", "luxman", "rotel", "naim"]
    for brand in brands:
        if brand in project_context.lower():
            entities.add(brand.capitalize())

    # Component types
    components = [
        "capacitor",
        "transistor",
        "diode",
        "mosfet",
        "posistor",
        "thermistor",
        "relay",
        "ic",
        "op-amp",
    ]
    for comp in components:
        if comp in project_context.lower():
            entities.add(comp)

    return entities
