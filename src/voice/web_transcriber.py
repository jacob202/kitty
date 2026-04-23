from dataclasses import dataclass
from pathlib import Path


@dataclass(eq=True)
class TranscriptionResult:
    text: str
    language: str | None
    duration_seconds: float | None


class WebTranscriber:
    def __init__(self, model_size: str = "base", device: str = "cpu", compute_type: str = "int8"):
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self._model = None

    def _load_model(self):
        if self._model is None:
            from faster_whisper import WhisperModel

            self._model = WhisperModel(self.model_size, device=self.device, compute_type=self.compute_type)
        return self._model

    def transcribe_file(self, audio_path: Path) -> TranscriptionResult:
        model = self._load_model()
        segments, info = model.transcribe(str(audio_path), beam_size=5, vad_filter=True)
        text = " ".join(segment.text.strip() for segment in segments).strip()
        if not text:
            raise ValueError("No speech detected")
        return TranscriptionResult(
            text=text,
            language=getattr(info, "language", None),
            duration_seconds=getattr(info, "duration", None),
        )
