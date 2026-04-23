"""
YAMNet-based audio event classifier for hardware diagnostics.

CRITICAL DESIGN: Model is NOT loaded in __init__. Loading TensorFlow
and YAMNet synchronously blocks the async event loop for 3-7 seconds
and pins ~500MB of wired memory on M1 8GB — catastrophic for an 8GB machine.

Instead: lazy-load on first classify call, run in executor, unload when done.
"""

import asyncio
from typing import Any

import numpy as np


class AcousticClassifier:
    """
    YAMNet-based audio event classifier for hardware diagnostics.

    CRITICAL DESIGN: Model is NOT loaded in __init__. Loading TensorFlow
    and YAMNet synchronously blocks the async event loop for 3-7 seconds
    and pins ~500MB of wired memory on M1 8GB — catastrophic for an 8GB machine.

    Instead: lazy-load on first classify call, run in executor, unload when done.
    """

    AUTOMOTIVE_CLASSES = {
        "Vehicle",
        "Engine",
        "Idling",
        "Accelerating, revving, vroom",
        "Mechanical fan",
        "Grinding metal",
        "Squeak",
        "Clunk",
    }
    ELECTRONICS_CLASSES = {
        "Buzz",
        "Hum",
        "Electric hum",
        "Sine wave",
        "Whir",
        "Crackle",
    }

    def __init__(self):
        # Intentionally empty — no model loading here
        self._model = None
        self._class_names: list | None = None
        self._model_loaded = False

    async def _ensure_model_loaded(self):
        """Lazy-loads YAMNet in a thread executor — never blocks the event loop."""
        if self._model_loaded:
            return
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._load_model_sync)

    def _load_model_sync(self):
        """Blocking model load — only called from run_in_executor."""
        try:
            import tensorflow as tf
            import tensorflow_hub as hub

            # Limit TF memory growth on M1 — critical for 8GB unified memory
            gpus = tf.config.list_physical_devices("GPU")
            for gpu in gpus:
                tf.config.experimental.set_memory_growth(gpu, True)
            self._model = hub.load("https://tfhub.dev/google/yamnet/1")
            self._class_names = self._get_class_names_sync()
            self._model_loaded = True
        except ImportError:
            raise ImportError(
                "tensorflow and tensorflow-hub required for acoustic classification. "
                "Run: pip install tensorflow tensorflow-hub"
            )

    def _get_class_names_sync(self) -> list:
        """Loads YAMNet class map — called once during model load."""
        import csv
        import urllib.request

        url = (
            "https://raw.githubusercontent.com/tensorflow/data/models/master"
            "/research/audioset/yamnet/yamnet_class_map.csv"
        )
        try:
            with urllib.request.urlopen(url, timeout=10) as response:
                reader = csv.DictReader(line.decode() for line in response)
                return [row["display_name"] for row in reader]
        except Exception:
            # Fallback: return index strings if network unavailable
            return [str(i) for i in range(521)]

    async def classify_file(self, audio_path: str) -> dict[str, Any]:
        """Main entry point — lazy loads model, runs inference, returns top predictions."""
        await self._ensure_model_loaded()
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._classify_sync, audio_path)

    def _classify_sync(self, audio_path: str) -> dict[str, Any]:
        """Blocking inference — only called from run_in_executor."""
        import librosa

        # YAMNet requires 16kHz mono
        waveform, _ = librosa.load(audio_path, sr=16000, mono=True)
        scores, _, _ = self._model(waveform)
        mean_scores = np.mean(scores.numpy(), axis=0)
        top5_indices = np.argsort(mean_scores)[-5:][::-1]
        predictions = []
        for i in top5_indices:
            name = self._class_names[i] if i < len(self._class_names) else str(i)
            predictions.append({"class": name, "confidence": round(float(mean_scores[i]), 4)})

        # Tag domain for context-aware routing
        top_classes = {p["class"] for p in predictions[:3]}
        domain = "unknown"
        if top_classes & self.AUTOMOTIVE_CLASSES:
            domain = "automotive"
        elif top_classes & self.ELECTRONICS_CLASSES:
            domain = "electronics"

        return {
            "top_predictions": predictions,
            "domain": domain,
            "model": "yamnet",
        }

    def unload_model(self):
        """
        Explicitly frees ~500MB of YAMNet model memory.
        Call this after inference when you won't classify again for a while.
        On M1 8GB this is mandatory, not optional.
        """
        if self._model_loaded:
            try:
                import tensorflow as tf

                tf.keras.backend.clear_session()
            except Exception:
                pass
            self._model = None
            self._class_names = None
            self._model_loaded = False
