"""
Kitty Voice Interface - Speech-to-Text using faster-whisper
Local, fast, privacy-preserving transcription
"""

import os
import tempfile
import wave

try:
    from faster_whisper import WhisperModel

    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False
    print("⚠️  faster-whisper not installed. Voice input disabled.")

try:
    import pyaudio

    PYAUDIO_AVAILABLE = True
except ImportError:
    PYAUDIO_AVAILABLE = False
    print("⚠️  pyaudio not installed. Audio recording disabled.")


class KittyEars:
    """
    Speech-to-Text for Kitty AI using faster-whisper
    Local processing, no data leaves your machine
    """

    def __init__(
        self,
        model_size: str = "base",
        device: str = "cpu",
        compute_type: str = "int8",
        sample_rate: int = 16000,
    ):
        """
        Initialize Kitty's ears (STT)

        Args:
            model_size: tiny, base, small, medium, large
            device: cpu or cuda
            compute_type: int8, float16, float32
            sample_rate: Audio sample rate (16kHz optimal for whisper)
        """
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.sample_rate = sample_rate
        self.model = None

        if WHISPER_AVAILABLE:
            try:
                self.model = WhisperModel(model_size, device=device, compute_type=compute_type)
                print(f"✅ KittyEars initialized ({model_size} model)")
            except Exception as e:
                print(f"⚠️  Failed to load whisper model: {e}")
        else:
            print("⚠️  Whisper not available. Install: pip install faster-whisper")

    def listen(self, duration: int = 5, push_to_talk: bool = True, save_audio: bool = False) -> str:
        """
        Listen to user speech and transcribe

        Args:
            duration: Recording duration in seconds
            push_to_talk: If True, wait for user to press Enter
            save_audio: If True, save the audio file for debugging

        Returns:
            Transcribed text
        """
        if not WHISPER_AVAILABLE or not PYAUDIO_AVAILABLE:
            return "[Voice input not available - missing dependencies]"

        if self.model is None:
            return "[Whisper model not loaded]"

        if push_to_talk:
            input("🎤 Press Enter to speak...")

        print("🎤 Listening...")

        # Record audio
        audio_data = self._record_audio(duration)

        if audio_data is None:
            return "[Recording failed]"

        # Save to temp file
        temp_file = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                temp_file = f.name
                self._save_wav(temp_file, audio_data)

            # Transcribe
            print("🧠 Transcribing...")
            segments, info = self.model.transcribe(temp_file, beam_size=5)

            text = " ".join([seg.text for seg in segments]).strip()

            if info.language:
                print(f"🌍 Detected language: {info.language}")

            if text:
                print(f'✅ Heard: "{text}"')
            else:
                print("⚠️  No speech detected")

            # Clean up
            if not save_audio and temp_file:
                os.unlink(temp_file)
            elif save_audio:
                print(f"💾 Audio saved: {temp_file}")

            return text if text else "[No speech detected]"

        except Exception as e:
            print(f"❌ Transcription error: {e}")
            if temp_file and os.path.exists(temp_file):
                os.unlink(temp_file)
            return f"[Error: {str(e)}]"

    def _record_audio(self, duration: int) -> bytes | None:
        """Record audio from microphone"""
        if not PYAUDIO_AVAILABLE:
            return None

        CHUNK = 1024
        FORMAT = pyaudio.paInt16
        CHANNELS = 1

        p = pyaudio.PyAudio()

        try:
            stream = p.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=self.sample_rate,
                input=True,
                frames_per_buffer=CHUNK,
            )

            frames = []
            for _ in range(0, int(self.sample_rate / CHUNK * duration)):
                data = stream.read(CHUNK, exception_on_overflow=False)
                frames.append(data)

            stream.stop_stream()
            stream.close()
            p.terminate()

            return b"".join(frames)

        except Exception as e:
            print(f"❌ Recording error: {e}")
            p.terminate()
            return None

    def _save_wav(self, filename: str, audio_data: bytes):
        """Save audio data to WAV file"""
        with wave.open(filename, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(self.sample_rate)
            wf.writeframes(audio_data)

    def is_available(self) -> bool:
        """Check if voice input is available"""
        return WHISPER_AVAILABLE and PYAUDIO_AVAILABLE and self.model is not None


class VoiceDetector:
    """
    Voice Activity Detection using Silero VAD
    Detects when user is speaking vs silence
    """

    def __init__(self):
        self.model = None
        self.utils = None
        self._load_model()

    def _load_model(self):
        """Load Silero VAD model"""
        try:
            import torch

            self.model, self.utils = torch.hub.load(
                repo_or_dir="snakers4/silero-vad",
                model="silero_vad",
                force_reload=False,
                verbose=False,
            )
            self.model.eval()
        except Exception as e:
            print(f"⚠️  Could not load VAD model: {e}")

    def is_speech(self, audio_chunk: bytes, sample_rate: int = 16000) -> bool:
        """
        Detect if audio chunk contains speech

        Args:
            audio_chunk: Raw audio bytes
            sample_rate: Audio sample rate

        Returns:
            True if speech detected
        """
        if self.model is None:
            return True  # Assume speech if VAD not available

        try:
            import numpy as np
            import torch

            # Convert bytes to numpy array
            audio_array = np.frombuffer(audio_chunk, dtype=np.int16)
            audio_tensor = torch.from_numpy(audio_array).float() / 32768.0

            # Get speech probability
            speech_prob = self.model(audio_tensor, sample_rate).item()

            return speech_prob > 0.5

        except Exception as e:
            print(f"VAD error: {e}")
            return True  # Default to speech on error


# Quick test
if __name__ == "__main__":
    ears = KittyEars(model_size="tiny")  # Use tiny for testing

    if ears.is_available():
        print("\n🎤 Voice Test Mode")
        print("Say something...\n")

        text = ears.listen(duration=3, push_to_talk=True)
        print(f"\n📝 Transcribed: {text}")
    else:
        print("❌ Voice input not available")
        print("Install dependencies:")
        print("  pip install faster-whisper pyaudio")
