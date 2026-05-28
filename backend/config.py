from pydantic_settings import BaseSettings
from pathlib import Path

SOUL_DIR = Path(__file__).parent.parent / "soul"


class Settings(BaseSettings):
    anthropic_api_key: str
    mem0_api_key: str = ""
    user_id: str = "default"

    # Model routing thresholds
    haiku_model: str = "claude-haiku-4-5-20251001"
    sonnet_model: str = "claude-sonnet-4-6"
    opus_model: str = "claude-opus-4-7"

    # Max tokens per tier
    haiku_max_tokens: int = 1024
    sonnet_max_tokens: int = 4096
    opus_max_tokens: int = 8192

    class Config:
        env_file = ".env"


settings = Settings()
