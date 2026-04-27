"""
Dynamic Model Loader for Kitty.
Remembers which MLX model works best for each task type,
and loads the optimal one with caching to avoid unnecessary swaps.
"""

import json
import time
from pathlib import Path
from typing import Optional, Dict
import mlx_lm

CONFIG_PATH = Path.home() / ".kitty_model_prefs.json"
DEFAULT_MODEL = "mlx-community/Llama-3.2-3B-Instruct-4bit"

# Mapping of task types to preferred models (update after benchmark!)
# You will set these based on your test results.
TASK_MODEL_MAP: Dict[str, str] = {
    "conversation": "mlx-community/Llama-3.2-3B-Instruct-4bit",
    "automotive": "mlx-community/Qwen2.5-3B-Instruct-4bit",   # adjust after test
    "fitness": "mlx-community/Llama-3.2-3B-Instruct-4bit",
    "growth": "mlx-community/Llama-3.2-3B-Instruct-4bit",
    "routing": "mlx-community/Qwen2.5-3B-Instruct-4bit",
    "code": "mlx-community/Qwen2.5-3B-Instruct-4bit",
    "general": DEFAULT_MODEL,
}

class ModelSwitcher:
    def __init__(self):
        self.current_model: Optional[str] = None
        self.load_time: Optional[float] = None
        self._load_preferences()

    def _load_preferences(self):
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH) as f:
                data = json.load(f)
                self.task_map = data.get("task_map", TASK_MODEL_MAP)
        else:
            self.task_map = TASK_MODEL_MAP
            self._save_preferences()

    def _save_preferences(self):
        CONFIG_PATH.parent.mkdir(exist_ok=True)
        with open(CONFIG_PATH, "w") as f:
            json.dump({"task_map": self.task_map, "last_updated": time.time()}, f, indent=2)

    def get_best_model(self, task_type: str) -> str:
        """Return the model assigned to a task, falling back to default."""
        return self.task_map.get(task_type, DEFAULT_MODEL)

    def load_if_needed(self, task_type: str) -> tuple:
        """Load the optimal model, reusing if already loaded. Returns (model_name, model, tokenizer)."""
        model_name = self.get_best_model(task_type)
        if model_name != self.current_model:
            if self.current_model:
                print(f"Switching from {self.current_model} to {model_name} for {task_type}")
            else:
                print(f"Loading {model_name} for {task_type}")
            model, tokenizer = mlx_lm.load(model_name)
            self.current_model = model_name
            self.load_time = time.time()
            return model_name, model, tokenizer
        else:
            print(f"Reusing cached {model_name}")
            model, tokenizer = mlx_lm.load(model_name)
            return model_name, model, tokenizer

    def update_preference(self, task_type: str, model_name: str):
        """After manual evaluation, update the preferred model for a task."""
        self.task_map[task_type] = model_name
        self._save_preferences()
        print(f"Updated {task_type} → {model_name}")

# Global instance
switcher = ModelSwitcher()