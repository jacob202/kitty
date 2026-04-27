"""
Model Preloader and Context Manager for Kitty.

This module handles:
1. Dynamic loading and unloading of MLX models to prevent OOM errors.
2. Explicit memory management (`mx.metal.clear_cache()`).
3. Preserving context (conversation history) across model swaps.
4. Preloading the next anticipated model if instructed.
"""

import json
import time
import gc
from pathlib import Path
from typing import Optional, Dict, List, Tuple, Any

import mlx.core as mx
from mlx_lm import load

CONFIG_PATH = Path.home() / ".kitty_model_prefs.json"

# Default fallback model
DEFAULT_MODEL = "mlx-community/Llama-3.2-3B-Instruct-4bit"

# Router model stays in memory at all times if possible
ROUTER_MODEL = "mlx-community/DeepSeek-R1-Distill-Qwen-1.5B-4bit"

# Mapping of task types to preferred models
TASK_MODEL_MAP: Dict[str, str] = {
    "conversation": "mlx-community/Llama-3.2-3B-Instruct-4bit",
    "automotive": "mlx-community/Qwen2.5-3B-Instruct-4bit",
    "research": "mlx-community/Qwen2.5-3B-Instruct-4bit",
    "routing": ROUTER_MODEL,
    "code": "mlx-community/Qwen2.5-3B-Instruct-4bit",
    "general": DEFAULT_MODEL,
}

class ModelPreloader:
    def __init__(self):
        # We hold the actual loaded models and tokenizers here
        # Format: { "model_id": (model, tokenizer) }
        self._loaded_models: Dict[str, Tuple[Any, Any]] = {}
        
        # Context/History per task type
        # Format: { "task_type": [{"role": "user", "content": "..."}] }
        self._task_contexts: Dict[str, List[Dict[str, str]]] = {}
        
        self._load_preferences()

    def _load_preferences(self):
        try:
            if CONFIG_PATH.exists():
                with open(CONFIG_PATH) as f:
                    data = json.load(f)
                    self.task_map = data.get("task_map", TASK_MODEL_MAP)
            else:
                self.task_map = TASK_MODEL_MAP
                self._save_preferences()
        except (json.JSONDecodeError, OSError) as e:
            print(f"[Warning] Failed to load preferences: {e}. Using defaults.")
            self.task_map = TASK_MODEL_MAP
            self._save_preferences()
        
        # Initialize empty contexts for all known tasks
        for task in self.task_map.keys():
            self._task_contexts[task] = []

    def _save_preferences(self):
        CONFIG_PATH.parent.mkdir(exist_ok=True)
        with open(CONFIG_PATH, "w") as f:
            json.dump({"task_map": self.task_map, "last_updated": time.time()}, f, indent=2)

    def get_best_model_id(self, task_type: str) -> str:
        """Return the model ID assigned to a task."""
        return self.task_map.get(task_type, DEFAULT_MODEL)

    def _free_model(self, model_id: str):
        """Unload a specific model from memory explicitly."""
        if model_id in self._loaded_models:
            print(f"[Memory Manager] Freeing {model_id} from VRAM...")
            del self._loaded_models[model_id]
            # Force Python garbage collection
            gc.collect()
            # Force MLX to clear the Metal GPU cache
            mx.metal.clear_cache()

    def unload_all_except(self, keep_model_ids: List[str]):
        """Unload all models except the ones explicitly requested to be kept."""
        to_remove = [mid for mid in self._loaded_models.keys() if mid not in keep_model_ids]
        for mid in to_remove:
            self._free_model(mid)

    def load_model_for_task(self, task_type: str) -> Tuple[Any, Any, str]:
        """
        Loads the required model for a task, evicting the previous model 
        to prevent Out-Of-Memory (OOM) errors. 
        Always attempts to keep the Router model warm if possible.
        """
        target_model_id = self.get_best_model_id(task_type)
        
        # If the model is already loaded, just return it
        if target_model_id in self._loaded_models:
            print(f"[Model Preloader] {target_model_id} is already loaded (Warm).")
            return self._loaded_models[target_model_id][0], self._loaded_models[target_model_id][1], target_model_id

        print(f"[Model Preloader] Preparing to load: {target_model_id} for '{task_type}'")

        # Evict other models. We try to keep the router loaded if it's not the target, 
        # but if we are memory constrained, we might need to evict it too.
        # For an 8GB-16GB Mac, loading ONE 3B/4B model and ONE 1.5B model is the absolute limit.
        keep_ids = [target_model_id]
        if target_model_id != ROUTER_MODEL:
            # We want to keep the router loaded alongside the specialist so routing is instant
            keep_ids.append(ROUTER_MODEL)
            
        self.unload_all_except(keep_ids)

        # Load the requested model
        print(f"[Model Preloader] Fetching weights to Metal GPU buffer: {target_model_id}...")
        start = time.time()
        model, tokenizer = load(target_model_id)
        self._loaded_models[target_model_id] = (model, tokenizer)
        
        print(f"[Model Preloader] Loaded in {time.time() - start:.2f}s.")
        return model, tokenizer, target_model_id

    def get_context(self, task_type: str) -> List[Dict[str, str]]:
        """Retrieve the conversation context/history for a specific task."""
        if task_type not in self._task_contexts:
            self._task_contexts[task_type] = []
        return self._task_contexts[task_type]

    def append_to_context(self, task_type: str, role: str, content: str, max_turns: int = 10):
        """
        Add a message to the task's context history.
        Keeps the context bounded to 'max_turns' to avoid massive KV cache growth over time.
        """
        if task_type not in self._task_contexts:
            self._task_contexts[task_type] = []
            
        self._task_contexts[task_type].append({"role": role, "content": content})
        
        # Truncate if it exceeds max_turns (a turn is a user+assistant pair, so *2)
        if len(self._task_contexts[task_type]) > max_turns * 2:
            # Keep system prompt if it was the first message? 
            # We assume system prompt is injected at generation time, so just slice.
            self._task_contexts[task_type] = self._task_contexts[task_type][-(max_turns * 2):]

    def clear_context(self, task_type: str):
        """Clear the history for a specific task."""
        self._task_contexts[task_type] = []
        print(f"[Context Manager] Cleared context for '{task_type}'.")

    def update_preference(self, task_type: str, model_id: str):
        """Update the preferred model for a task."""
        self.task_map[task_type] = model_id
        self._save_preferences()
        print(f"[Model Preloader] Updated preference: {task_type} -> {model_id}")

# Global instance
preloader = ModelPreloader()
