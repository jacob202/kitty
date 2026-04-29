"""
MLX Model Optimizer - Performance utilities for Kitty MLX models

Provides:
- Smart model caching
- Memory management
- Lazy loading
- Prefetching
"""

import json
import os
import time
from pathlib import Path
from typing import Dict, Optional, Tuple, Any
from functools import lru_cache

import mlx.core as mx
from mlx_lm import load


CONFIG_PATH = Path.home() / ".kitty_model_prefs.json"
OPT_CONFIG = Path(__file__).parent.parent.parent / "config" / "mlx_optimization.json"


class MLXOptimizer:
    def __init__(self):
        self._cache: Dict[str, Tuple[Any, Any, float]] = {}
        self._load_config()
        self._load_optimization_config()

    def _load_config(self):
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH) as f:
                self.prefs = json.load(f)
        else:
            self.prefs = {}

    def _load_optimization_config(self):
        if OPT_CONFIG.exists():
            with open(OPT_CONFIG) as f:
                self.opt_config = json.load(f)
        else:
            self.opt_config = {}

    def get_model_config(self, task: str) -> Dict:
        return self.opt_config.get("model_configs", {}).get(task, {})

    def load_model(
        self,
        model_id: str,
        lazy: bool = True,
        use_fp16: bool = True
    ) -> Tuple[Any, Any]:
        """Load model with optimizations."""
        cache_key = f"{model_id}:{lazy}:{use_fp16}"

        if cache_key in self._cache:
            model, tokenizer, _ = self._cache[cache_key]
            print(f"[MLX Optimizer] Cache hit: {model_id}")
            return model, tokenizer

        print(f"[MLX Optimizer] Loading: {model_id}")
        start = time.time()

        model, tokenizer = load(
            model_id,
            tokenizer_config={"trust_remote_code": True}
        )

        load_time = time.time() - start
        self._cache[cache_key] = (model, tokenizer, load_time)

        print(f"[MLX Optimizer] Loaded in {load_time:.2f}s")
        return model, tokenizer

    def get_cached_models(self) -> Dict[str, float]:
        """Return cached models and their load times."""
        return {
            key: info[2]
            for key, info in self._cache.items()
        }

    def clear_cache(self):
        """Clear model cache to free memory."""
        self._cache.clear()
        mx.clear_cache()
        print("[MLX Optimizer] Cache cleared")

    def get_memory_usage(self) -> Dict[str, float]:
        """Get current memory usage."""
        return {
            "used_gb": mx.get_active_memory() / (1024**3),
            "peak_gb": mx.get_peak_memory() / (1024**3),
        }


def smart_load(task: str) -> Tuple[Any, Any]:
    """Load the optimal model for a given task."""
    optimizer = MLXOptimizer()
    config = optimizer.get_model_config(task)

    model_id = config.get("model", "mlx-community/Qwen3.5-4B-4bit")
    use_fp16 = config.get("use_fp16", True)

    return optimizer.load_model(model_id, use_fp16=use_fp16)


def prefetch_models(model_ids: list):
    """Preload models in background."""
    optimizer = MLXOptimizer()
    for model_id in model_ids:
        try:
            optimizer.load_model(model_id, lazy=False)
        except Exception as e:
            print(f"[Prefetch] Failed to load {model_id}: {e}")


def get_model_for_task(task: str, model_map: Dict[str, str]) -> str:
    """Get model ID for a task, with fallback to default."""
    return model_map.get(task, model_map.get("general", "mlx-community/Qwen3.5-4B-4bit"))


if __name__ == "__main__":
    opt = MLXOptimizer()
    print("MLX Optimizer initialized")
    print(f"  Cached models: {len(opt._cache)}")
    print(f"  Memory: {opt.get_memory_usage()}")