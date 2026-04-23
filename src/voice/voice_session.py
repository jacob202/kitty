"""
Kitty Voice Assistant - Full Integration
Combines Ears (STT) + Voice (TTS) for complete voice interface
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from voice.kitty_ears import KittyEars
from voice.kitty_voice import KittyVoice


class VoiceSession:
    """
    Complete voice interaction session
    Listen → Process → Speak
    """

    def __init__(self, stt_model: str = "base", voice: str = "lessac", process_callback=None):
        """
        Initialize voice session

        Args:
            stt_model: Whisper model size (tiny/base/small)
            voice: Piper voice name
            process_callback: Function to process text and return response
        """
        print("🎙️  Initializing Voice Session...")

        self.ears = KittyEars(model_size=stt_model)
        self.voice = KittyVoice(voice=voice)
        self.process_callback = process_callback

        self.session_active = False

        # Check availability
        if not self.ears.is_available():
            print("⚠️  Speech-to-text not available")
        if not self.voice.is_available():
            print("⚠️  Text-to-speech not available")

    def start(self, continuous: bool = True):
        """
        Start voice session

        Args:
            continuous: If True, keep listening after each response
        """
        if not self.ears.is_available() and not self.voice.is_available():
            print("❌ Voice session cannot start - no voice components available")
            return

        self.session_active = True

        print("\n🐱✨ Kitty Voice Mode")
        print("Say 'exit', 'quit', or 'goodbye' to stop")
        print("-" * 50)

        # Welcome message
        if self.voice.is_available():
            self.voice.speak("Hello! I'm Kitty. I'm listening.")
        else:
            print("Kitty: Hello! I'm listening.")

        while self.session_active:
            try:
                # Listen
                if self.ears.is_available():
                    user_input = self.ears.listen(duration=5, push_to_talk=True)
                else:
                    user_input = input("\nYou: ").strip()

                # Check exit commands
                if user_input.lower() in ["exit", "quit", "goodbye", "stop"]:
                    self.stop()
                    break

                # Skip empty input
                if not user_input or user_input.startswith("["):
                    continue

                # Process
                if self.process_callback:
                    response = self.process_callback(user_input)
                else:
                    response = f"You said: {user_input}"

                # Speak response
                print(f"Kitty: {response}")

                if self.voice.is_available():
                    self.voice.speak(response)

                # Break if not continuous
                if not continuous:
                    break

            except KeyboardInterrupt:
                print("\n👋 Interrupted")
                self.stop()
                break
            except Exception as e:
                print(f"❌ Session error: {e}")
                continue

    def stop(self):
        """Stop voice session"""
        self.session_active = False

        if self.voice.is_available():
            self.voice.speak("Goodbye!")
        else:
            print("Kitty: Goodbye!")

        print("\n🎙️  Voice session ended")

    def is_fully_available(self) -> bool:
        """Check if both STT and TTS are available"""
        return self.ears.is_available() and self.voice.is_available()


# Simple test
if __name__ == "__main__":
    # Example process callback
    def simple_echo(text):
        """Simple echo for testing"""
        responses = {
            "hello": "Hello there! Nice to meet you!",
            "how are you": "I'm doing great, thanks for asking!",
            "what is your name": "I'm Kitty, your personal AI assistant!",
        }

        text_lower = text.lower()
        for key, response in responses.items():
            if key in text_lower:
                return response

        return f"I heard you say: {text}"

    # Start session
    session = VoiceSession(
        stt_model="tiny",  # Use tiny for faster testing
        voice="lessac",
        process_callback=simple_echo,
    )

    if session.is_fully_available():
        session.start(continuous=True)
    else:
        print("\n⚠️  Voice components not fully available")
        print("Install dependencies:")
        print("  pip install faster-whisper pyaudio")
        print("  Download Piper: https://github.com/rhasspy/piper")
