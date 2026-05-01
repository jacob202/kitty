"""Kitty API Blueprints."""
from .eval_routes import eval_bp
from .ai_dev_routes import ai_dev_bp
from .bom_routes import bom_bp
from .core_routes import core_bp
from .hardware_routes import hardware_bp
from .memory_product_routes import memory_product_bp
from .memory_routes import memory_bp
from .news_routes import news_bp
from .reasoning_routes import reasoning_bp
from .settings_routes import settings_bp
from .streaming_routes import streaming_bp
from .swarm_routes import swarm_bp
from .system_routes import system_bp
from .voice_routes import voice_bp
from .brief import brief_bp
from .commands import commands_bp

__all__ = [
    "ai_dev_bp",
    "eval_bp",
    "bom_bp",
    "core_bp",
    "hardware_bp",
    "memory_product_bp",
    "memory_bp",
    "news_bp",
    "reasoning_bp",
    "settings_bp",
    "streaming_bp",
    "swarm_bp",
    "system_bp",
    "voice_bp",
    "brief_bp",
    "commands_bp",
]
