"""
Affective Computing Module for Kitty.

Provides emotional analysis, persona modulation, and Match Energy integration.

Main exports:
- EmotiveMirror: Real-time emotion analysis and response modulation
- PersonaDirective: Result of emotion analysis
- get_emotive_mirror(): Get singleton instance
- quick_analyze(): Convenience function for single inputs
- quick_modulate(): Convenience function for response modulation
"""

from src.affective.emotive_mirror import (
    HONEY_BADGER_PHRASES,
    PERSONA_CONFIGS,
    EmotiveMirror,
    PersonaDirective,
    TypingEvent,
    get_emotive_mirror,
    quick_analyze,
    quick_modulate,
)

__all__ = [
    # Classes
    "EmotiveMirror",
    "PersonaDirective",
    "TypingEvent",
    # Constants
    "PERSONA_CONFIGS",
    "HONEY_BADGER_PHRASES",
    # Functions
    "get_emotive_mirror",
    "quick_analyze",
    "quick_modulate",
]
