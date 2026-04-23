"""
Gemini Voice Interface - Text-to-Speech using Gemini API
Cloud-based high-quality synthesis with multiple voices

NOTE: As of Apr 2026, Gemini does not have native TTS API.
This is a placeholder/integration point for when it becomes available.
Current fallback: use gTTS (Google Text-to-Speech) via google cloud API.
"""

import logging
import os
import tempfile
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

try:
    from gtts import gTTS as _gTTS
    gtts_module = _gTTS.__module__
    gTTS = _gTTS
    HAS_GTTS = True
except ImportError:
    gTTS = None
    gtts_module = None
    HAS_GTTS = False


VoiceType = Literal["male", "female", "neutral"]


class GeminiVoice:
    """
    Text-to-Speech using Google Cloud TTS (compatible interface for future Gemini TTS).

    When Gemini native TTS becomes available, this will use google.genai.Client.
    For now, falls back to gTTS for compatibility.

    Usage:
        voice = GeminiVoice(voice_type="female", speed=1.1)
        voice.speak("Hello from Kitty!")
        voice.save_to_file("Hello from Kitty!", "output.wav")
    """

    # Voice mapping for gTTS (will be replaced with Gemini voices when available)
    VOICE_LANGUAGES = {
        "male": "en-us",  # gTTS doesn't differentiate gender, so using accents
        "female": "en-gb",  # British accent as female proxy
        "neutral": "en-au",  # Australian accent as neutral proxy
    }

    def __init__(
        self,
        voice_type: VoiceType = "neutral",
        speed: float = 1.0,
        api_key: str | None = None,
    ):
        """
        Initialize Gemini voice (TTS).

        Args:
            voice_type: Voice gender/style (male, female, neutral)
            speed: Speech rate (0.25-4.0, where 1.0 is normal)
            api_key: Gemini API key (reads from GEMINI_API_KEY env if not provided)
        """
        self.voice_type = voice_type
        self.speed = max(0.25, min(4.0, speed))  # Clamp to valid range
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")

        if not self.api_key:
            logger.warning("GEMINI_API_KEY not set, TTS may fail")

        if not HAS_GTTS:
            logger.error(
                "gTTS not installed. Install: pip install gTTS\n"
                "Note: This will be replaced with Gemini native TTS when available."
            )

        logger.info(f"GeminiVoice initialized ({voice_type} voice, {speed}x speed)")

    def synthesize(self, text: str) -> bytes | None:
        """
        Synthesize speech from text using gTTS (Gemini TTS placeholder).

        Args:
            text: Text to synthesize

        Returns:
            Audio bytes in MP3 format, or None if synthesis fails
        """
        if not HAS_GTTS:
            logger.error("gTTS not available")
            return None

        try:
            lang = self.VOICE_LANGUAGES.get(self.voice_type, "en-us")
            tts = gTTS(text=text, lang=lang, slow=(self.speed < 0.9))

            # Save to temp file and read back (gTTS doesn't provide bytes directly)
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                temp_path = f.name

            tts.save(temp_path)
            audio_bytes = Path(temp_path).read_bytes()
            Path(temp_path).unlink()  # Cleanup

            return audio_bytes

        except Exception as e:
            logger.error(f"TTS synthesis failed: {e}")
            return None

    def speak(self, text: str, play_audio: bool = True) -> bool:
        """
        Synthesize and optionally play audio.

        Args:
            text: Text to speak
            play_audio: If True, play audio immediately (requires afplay/mpg123)

        Returns:
            True if synthesis succeeded, False otherwise
        """
        audio_bytes = self.synthesize(text)
        if not audio_bytes:
            return False

        if play_audio:
            try:
                # Try macOS afplay first
                import subprocess

                with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                    f.write(audio_bytes)
                    temp_path = f.name

                # macOS afplay or Linux mpg123
                player = "afplay" if os.path.exists("/usr/bin/afplay") else "mpg123"
                subprocess.run([player, temp_path], check=True, capture_output=True)
                Path(temp_path).unlink()

            except Exception as e:
                logger.warning(f"Audio playback failed: {e}")

        return True

    def save_to_file(self, text: str, output_path: str) -> bool:
        """
        Synthesize speech and save to file.

        Args:
            text: Text to synthesize
            output_path: Output file path (.mp3 or .wav)

        Returns:
            True if successful, False otherwise
        """
        audio_bytes = self.synthesize(text)
        if not audio_bytes:
            return False

        try:
            Path(output_path).write_bytes(audio_bytes)
            logger.info(f"Saved audio to {output_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to save audio: {e}")
            return False

    @staticmethod
    def list_voices() -> dict[str, str]:
        """
        List available voices (placeholder for Gemini TTS API).

        Returns:
            Dict mapping voice_type -> description
        """
        return {
            "male": "Male voice (US English accent)",
            "female": "Female voice (GB English accent)",
            "neutral": "Neutral voice (AU English accent)",
        }


def test_gemini_voice():
    """Test Gemini voice synthesis."""
    import sys

    if not HAS_GTTS:
        print("gTTS not installed. Run: pip install gTTS")
        sys.exit(1)

    voice = GeminiVoice(voice_type="female", speed=1.1)
    text = "Hello! I'm Kitty, your AI assistant. How can I help you today?"

    print(f"Synthesizing: {text}")
    if voice.speak(text, play_audio=False):
        print("✅ Synthesis successful")

        # Save to file
        output = "test_gemini_voice.mp3"
        if voice.save_to_file(text, output):
            print(f"✅ Saved to {output}")
    else:
        print("❌ Synthesis failed")


if __name__ == "__main__":
    test_gemini_voice()
