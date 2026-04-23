import asyncio

import numpy as np

try:
    import sounddevice as sd
except ModuleNotFoundError:
    sd = None


class AcousticAnalyzer:
    """
    Captures raw audio from the Mac's microphone, applies DSP windowing,
    and extracts the dominant frequencies to diagnose hardware issues
    (e.g., 60Hz ground loops vs. 120Hz filter cap failures).
    """

    def __init__(self, sample_rate=44100, duration=3.0):
        self.sample_rate = sample_rate
        self.duration = duration

    async def listen_and_analyze(self) -> dict:
        loop = asyncio.get_running_loop()
        print("[System] 🎙️ Kitty is listening to the hardware...")
        audio_data = await loop.run_in_executor(None, self._record_audio)
        return self._extract_frequency_profile(audio_data)

    def _record_audio(self) -> np.ndarray:
        if sd is None:
            raise RuntimeError("sounddevice is required for live microphone capture")
        frames = int(self.duration * self.sample_rate)
        recording = sd.rec(frames, samplerate=self.sample_rate, channels=1, dtype="float64")
        sd.wait()
        return recording.flatten()

    def _extract_frequency_profile(self, audio_data: np.ndarray) -> dict:
        windowed_data = audio_data * np.hamming(len(audio_data))
        spectrum = np.fft.rfft(windowed_data)
        frequencies = np.fft.rfftfreq(len(windowed_data), 1 / self.sample_rate)
        magnitudes = np.abs(spectrum)
        peak_indices = np.argsort(magnitudes)[-3:][::-1]
        dominant_freqs = frequencies[peak_indices]

        return {
            "primary_frequency_hz": round(dominant_freqs[0], 1),
            "secondary_harmonics_hz": [round(f, 1) for f in dominant_freqs[1:]],
            "amplitude_variance": "steady" if np.var(magnitudes) < 0.5 else "erratic",
            "raw_payload_ready": True,
        }
