import asyncio
import os

import numpy as np


class FileAcousticAnalyzer:
    """
    Ingests audio files recorded on a phone, normalizes the format,
    and applies chunked FFT DSP to extract diagnostic frequency profiles.

    CRITICAL: Uses librosa.stream() to process audio in 5-second chunks,
    preventing OOM crashes on M1 8GB for long recordings (>5 minutes).
    Each chunk is processed and freed before the next is loaded.
    """

    def __init__(self, temp_dir="/tmp/kitty_audio", chunk_duration_sec: float = 5.0):
        self.temp_dir = temp_dir
        self.chunk_duration = chunk_duration_sec
        if not os.path.exists(self.temp_dir):
            os.makedirs(self.temp_dir)

    async def analyze_file(self, file_path: str) -> dict:
        print(f"[System] Ingesting audio from {os.path.basename(file_path)}...")
        wav_path = await self._normalize_audio_format(file_path)
        loop = asyncio.get_running_loop()
        # Run blocking FFT math in executor — never blocks the event loop
        profile = await loop.run_in_executor(None, self._analyze_chunked, wav_path)
        if wav_path != file_path and os.path.exists(wav_path):
            os.remove(wav_path)
        return profile

    def _analyze_chunked(self, wav_path: str) -> dict:
        """
        Streams audio in chunk_duration_sec windows via librosa.stream().
        Accumulates per-chunk FFT peaks then aggregates — max RAM = one chunk.
        """
        import librosa

        sr = 44100
        chunk_samples = int(self.chunk_duration * sr)
        dominant_freqs = []
        magnitude_variances = []
        chunks_processed = 0

        try:
            stream = librosa.stream(
                wav_path,
                block_length=chunk_samples,
                frame_length=chunk_samples,
                hop_length=chunk_samples,
            )
            for y_block in stream:
                if len(y_block) < 1024:
                    continue
                # Window + FFT on this chunk only — previous chunk freed by GC
                windowed = y_block * np.hamming(len(y_block))
                spectrum = np.fft.rfft(windowed)
                freqs = np.fft.rfftfreq(len(y_block), 1 / sr)
                mags = np.abs(spectrum)
                peak_idx = np.argmax(mags)
                dominant_freqs.append(freqs[peak_idx])
                magnitude_variances.append(float(np.var(mags)))
                chunks_processed += 1
                # Explicitly del to free memory before next chunk
                del windowed, spectrum, mags
        except Exception as e:
            return {
                "error": str(e),
                "primary_frequency_hz": 0.0,
                "secondary_harmonics_hz": [],
                "duration_seconds": 0.0,
                "amplitude_variance": "unknown",
            }

        if not dominant_freqs:
            return {
                "primary_frequency_hz": 0.0,
                "secondary_harmonics_hz": [],
                "duration_seconds": 0.0,
                "amplitude_variance": "unknown",
            }

        avg_variance = float(np.mean(magnitude_variances))
        return {
            "primary_frequency_hz": round(float(np.mean(dominant_freqs)), 1),
            "secondary_harmonics_hz": [],
            "duration_seconds": round(chunks_processed * self.chunk_duration, 2),
            "amplitude_variance": "steady" if avg_variance < 0.5 else "erratic",
        }

    def _extract_frequency_profile(self, audio_data: np.ndarray, sample_rate: int = 44100) -> dict:
        """Extract a simple FFT profile from an in-memory audio buffer."""
        if len(audio_data) == 0:
            return {
                "primary_frequency_hz": 0.0,
                "secondary_harmonics_hz": [],
                "duration_seconds": 0.0,
                "amplitude_variance": "unknown",
            }

        windowed = audio_data * np.hamming(len(audio_data))
        spectrum = np.fft.rfft(windowed)
        freqs = np.fft.rfftfreq(len(audio_data), 1 / sample_rate)
        mags = np.abs(spectrum)
        peak_indices = np.argsort(mags)[-3:][::-1]
        dominant_freqs = freqs[peak_indices]

        return {
            "primary_frequency_hz": round(float(dominant_freqs[0]), 1),
            "secondary_harmonics_hz": [round(float(f), 1) for f in dominant_freqs[1:]],
            "duration_seconds": round(len(audio_data) / sample_rate, 2),
            "amplitude_variance": "steady" if float(np.var(mags)) < 0.5 else "erratic",
        }

    async def _normalize_audio_format(self, input_path: str) -> str:
        """Uses ffmpeg to convert compressed phone audio to a raw 44.1kHz mono WAV."""
        if input_path.lower().endswith(".wav"):
            return input_path
        output_path = os.path.join(self.temp_dir, "normalized_target.wav")
        cmd = ["ffmpeg", "-y", "-i", input_path, "-ac", "1", "-ar", "44100", output_path]
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await process.communicate()
        if process.returncode != 0:
            raise Exception("Failed to convert phone audio. Is ffmpeg installed?")
        return output_path
