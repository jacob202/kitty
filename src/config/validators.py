"""Config validation with Pydantic."""

from pathlib import Path
from pydantic import BaseModel, Field
import json


class KittySettings(BaseModel):
    """Main app settings."""
    port: int = Field(default=5001, ge=1024, le=65535)
    debug: bool = False
    log_level: str = "INFO"
    model: str = "qwen3.5"
    session_timeout: int = 3600


class HardwareTrigger(BaseModel):
    """Hardware trigger config."""
    cpu_enabled: bool = True
    gpu_enabled: bool = True
    min_memory_gb: int = 8


class DomainRouting(BaseModel):
    """Domain to specialist routing."""
    domain: str
    specialist: str
    enabled: bool = True


def load_settings() -> KittySettings:
    """Load and validate settings."""
    config_file = Path("config/kitty_settings.json")
    if config_file.exists():
        data = json.loads(config_file.read_text())
        return KittySettings(**data)
    return KittySettings()


def validate_config(name: str) -> bool:
    """Validate a config file."""
    validators = {
        "kitty_settings": KittySettings,
    }
    
    config_file = Path(f"config/{name}.json")
    if not config_file.exists():
        return False
    
    if name in validators:
        data = json.loads(config_file.read_text())
        validators[name](**data)  # Raises if invalid
        return True
    
    return True  # Unknown config, skip


# Test validation
if __name__ == "__main__":
    settings = load_settings()
    print(f"Port: {settings.port}")
    print(f"Debug: {settings.debug}")
    print(f"Model: {settings.model}")
    print("✓ Config validation working")