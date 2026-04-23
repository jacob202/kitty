"""
Model calling abstraction for better separation of concerns.
"""

import logging
import re

try:
    from src.utils.performance_hooks import patch_model_caller

    _PERF_HOOKS_AVAILABLE = True
except ImportError:
    _PERF_HOOKS_AVAILABLE = False

logger = logging.getLogger(__name__)


class ModelCaller:
    def __init__(self, supervisor):
        self.supervisor = supervisor
        self._CTRL_RE = re.compile(
            r"\x1b\[[0-9;]*[a-zA-Z]|\x1b\][^\x07]*\x07|[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]"
        )
        # Wire performance tracking
        if _PERF_HOOKS_AVAILABLE:
            try:
                patch_model_caller(self)
            except Exception:
                pass  # Non-fatal

    def call_with_fallback(
        self,
        prompt: str,
        system_prompt: str | None = None,
        model: str = "flash",
        use_history: bool = True,
    ):
        """Call model with automatic fallback on failure. Falls back to flash model only once to avoid infinite loops."""
        try:
            if model == "claude":
                return self.supervisor._stream_claude(
                    prompt, system_prompt or "", use_history=use_history
                )
            elif model == "flash":
                flash_model = self.supervisor.config.get(
                    "flash_model", "google/gemini-2.0-flash-001"
                )
                return self.supervisor._stream_openrouter(
                    prompt, system_prompt, model=flash_model, use_history=use_history
                )
            elif model == "local":
                return self.supervisor._stream_ollama(prompt)
            elif model == "mlx":
                return self.supervisor._stream_mlx(
                    prompt, system_prompt, use_history=use_history
                )
            else:
                return self.supervisor._stream_openrouter(
                    prompt, system_prompt, model=model, use_history=use_history
                )
        except Exception as e:
            flash_model_name = self.supervisor.config.get(
                "flash_model", "google/gemini-2.0-flash-001"
            )
            if model == "flash" or model == flash_model_name:
                raise RuntimeError(f"Flash model {flash_model_name} also failed: {e}") from e
            logger.warning(f"Model {model} failed: {e}, trying flash fallback...")
            return self.supervisor._stream_openrouter(
                prompt, system_prompt, model=flash_model_name, use_history=use_history
            )
