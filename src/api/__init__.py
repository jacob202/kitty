"""Kitty API Blueprints."""

from .eval_routes import eval_bp
from .bom_routes import bom_bp
from .core_routes import core_bp
from .hardware_routes import hardware_bp
from .honcho_routes import honcho_bp
from .memory_product_routes import memory_product_bp
from .memory_routes import memory_bp
from .reasoning_routes import reasoning_bp
from .settings_routes import settings_bp
from .streaming_routes import streaming_bp
from .swarm_routes import swarm_bp
from .system_routes import system_bp
from .voice_routes import voice_bp

__all__ = [
    "eval_bp",
    "bom_bp",
    "core_bp",
    "hardware_bp",
    "honcho_bp",
    "memory_bp",
    "memory_product_bp",
    "reasoning_bp",
    "settings_bp",
    "streaming_bp",
    "swarm_bp",
    "system_bp",
    "voice_bp",
]
