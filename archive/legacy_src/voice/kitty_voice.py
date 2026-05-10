"""
Kitty Voice Interface - Text-to-Speech using Piper
Lightweight, local, multiple voices
"""

import os
import platform
import subprocess
import tempfile


class KittyVoice:
    """
    Text-to-Speech for Kitty AI using Piper
    Local synthesis, no cloud, multiple voice options
    """

    # Default voice models available
    VOICES = {
        "lessac": "en_US-lessac-medium",
        "amy": "en_GB-amy-medium",
        "arctic": "en_US-arctic-medium",
        "danny": "en_US-danny-low",
        "joe": "en_US-joe-medium",
        "kathleen": "en_US-kathleen-low",
        "kristin": "en_US-kristin-medium",
        "ljspeech": "en_US-ljspeech-medium",
        "ryan": "en_US-ryan-medium",
    }

    def __init__(
        self,
        voice: str = "lessac",
        piper_path: str | None = None,
        voices_dir: str | None = None,
    ):
        """
        Initialize Kitty's voice (TTS)

        Args:
            voice: Voice name (lessac, amy, arctic, etc.)
            piper_path: Path to piper executable
            voices_dir: Directory containing voice models
        """
        self.voice = voice
        self.piper_path = piper_path or self._find_piper()
        self.voices_dir = voices_dir or "./voices"

        # Ensure voice is valid
        if voice not in self.VOICES:
            print(f"⚠️  Unknown voice '{voice}', using 'lessac'")
            self.voice = "lessac"

        self.voice_model = self.VOICES[self.voice]

        # Check if piper is available
        if self.piper_path and os.path.exists(self.piper_path):
            print(f"✅ KittyVoice initialized ({voice} voice)")
        else:
            print("⚠️  Piper not found. TTS disabled.")
            print("   Install: https://github.com/rhasspy/data/piper/releases")

    def _find_piper(self) -> str | None:
        """Find piper executable in common locations"""
        possible_paths = [
            "./data/piper/piper",
            "./data/piper/piper.exe",
            "/usr/local/bin/piper",
            "/usr/bin/piper",
            "~/bin/piper",
            "~/data/piper/piper",
        ]

        for path in possible_paths:
            expanded = os.path.expanduser(path)
            if os.path.exists(expanded):
                return expanded

        # Try which/where command
        try:
            result = subprocess.run(
                ["which", "piper"] if platform.system() != "Windows" else ["where", "piper"],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                return result.stdout.strip().split("\n")[0]
        except Exception:
            pass

        return None

    def speak(self, text: str, save_file: str | None = None) -> bool:
        """
        Speak text aloud using Piper TTS

        Args:
            text: Text to speak
            save_file: If provided, save audio to this path instead of playing

        Returns:
            True if successful
        """
        if not self.piper_path or not os.path.exists(self.piper_path):
            print("❌ Piper not available")
            return False

        if not text or not text.strip():
            print("⚠️  Empty text, nothing to speak")
            return False

        # Clean text (remove emojis, limit length)
        text = self._clean_text(text)

        # Create output file
        if save_file:
            output_file = save_file
        else:
            temp_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            output_file = temp_file.name
            temp_file.close()

        try:
            # Build command
            voice_path = f"{self.voices_dir}/{self.voice_model}.onnx"

            cmd = [self.piper_path, "--model", voice_path, "--output_file", output_file]

            # Run piper
            process = subprocess.Popen(
                cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )

            stdout, stderr = process.communicate(input=text.encode(), timeout=30)

            if process.returncode != 0:
                print(f"❌ Piper error: {stderr.decode()}")
                return False

            # Play audio if not saving
            if not save_file:
                self._play_audio(output_file)
                os.unlink(output_file)
            else:
                print(f"💾 Audio saved: {output_file}")

            return True

        except subprocess.TimeoutExpired:
            print("❌ TTS timeout")
            return False
        except Exception as e:
            print(f"❌ TTS error: {e}")
            return False

    def _clean_text(self, text: str) -> str:
        """Clean text for TTS"""
        # Remove emojis (simplify for now)
        import re

        text = re.sub(r"[^\x00-\x7F]+", "", text)

        # Limit length (Piper works best with shorter phrases)
        if len(text) > 500:
            text = text[:497] + "..."

        return text.strip()

    def _play_audio(self, audio_file: str):
        """Play audio file (platform-specific)"""
        system = platform.system()

        try:
            if system == "Darwin":  # macOS
                subprocess.run(["afplay", audio_file], check=True)
            elif system == "Linux":
                # Try multiple players
                for player in ["aplay", "paplay", "play"]:
                    try:
                        subprocess.run([player, audio_file], check=True)
                        return
                    except Exception:
                        continue
                print("⚠️  No audio player found (install aplay or paplay)")
            elif system == "Windows":
                import winsound

                winsound.PlaySound(audio_file, winsound.SND_FILENAME)
        except Exception as e:
            print(f"⚠️  Could not play audio: {e}")

    def list_voices(self):
        """List available voices"""
        print("\n🎙️  Available Voices:")
        for name, model in self.VOICES.items():
            marker = "✅" if name == self.voice else "  "
            print(f"   {marker} {name}: {model}")
        print()

    def is_available(self) -> bool:
        """Check if TTS is available"""
        return self.piper_path is not None and os.path.exists(self.piper_path)

    def download_voice(self, voice: str = None):
        """
        Download voice model (placeholder - manual download required)

        Voice models must be downloaded from:
        https://github.com/rhasspy/data/piper/releases/tag/2023.11.14-2
        """
        voice = voice or self.voice
        if voice not in self.VOICES:
            print(f"❌ Unknown voice: {voice}")
            return

        model = self.VOICES[voice]

        print(f"\n📥 To download the {voice} voice:")
        print("   1. Visit: https://github.com/rhasspy/data/piper/releases/tag/2023.11.14-2")
        print(f"   2. Download: {model}.onnx and {model}.onnx.json")
        print(f"   3. Place in: {self.voices_dir}/")
        print()


# Quick test
if __name__ == "__main__":
    voice = KittyVoice()

    if voice.is_available():
        voice.list_voices()

        test_phrases = [
            "Hello, I'm Kitty!",
            "I can speak now!",
            "The quick brown fox jumps over the lazy dog.",
        ]

        for phrase in test_phrases:
            print(f'\n🗣️  Speaking: "{phrase}"')
            voice.speak(phrase)
    else:
        print("❌ Text-to-speech not available")
        print("Install Piper from: https://github.com/rhasspy/piper")
