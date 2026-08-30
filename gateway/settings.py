"""Pydantic-settings model for Kitty gateway configuration.

All env vars the gateway reads are declared here.  Call ``get_settings()``
(never import the Settings class directly) to get a fresh instance that
re-reads from the current os.environ, which keeps pytest monkeypatch working.
"""

from __future__ import annotations

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        case_sensitive=True,
    )

    # Gateway process
    GATEWAY_HOST: str = "127.0.0.1"
    GATEWAY_PORT: int = 8000

    # LiteLLM proxy
    LITELLM_HOST: str = "127.0.0.1"
    LITELLM_PORT: int = 8001

    # Auth (SecretStr so values are masked in repr/logs)
    GATEWAY_SECRET: SecretStr | None = None
    LITELLM_KEY: SecretStr | None = None

    # Runtime env flag
    KITTY_ENV: str = "local"

    # LLM chain timing
    KITTY_PROVIDER_CONNECT_TIMEOUT: float = 5.0
    KITTY_LLM_CHAIN_DEADLINE: float = 90.0

    # Provider API keys (SecretStr; None means key not configured)
    OPENAI_API_KEY: SecretStr | None = None
    GEMINI_API_KEY: SecretStr | None = None
    OPENROUTER_API_KEY: SecretStr | None = None
    NVIDIA_API_KEY: SecretStr | None = None
    AGENTROUTER_API_KEY: SecretStr | None = None
    AGENT_ROUTER_TOKEN: SecretStr | None = None

    # LLM routing — model slugs and base URLs
    KITTY_OPENROUTER_CHEAP: str = "deepseek/deepseek-v4-flash"
    KITTY_OPENROUTER_DIRECT_MODEL: str = ""
    KITTY_OPENAI_FALLBACK_MODEL: str = "gpt-4o-mini"
    OPENAI_API_BASE: str = "https://api.openai.com/v1"
    KITTY_GEMINI_MODEL: str = "gemini-2.5-flash-image"
    AGENTROUTER_MODEL: str = ""
    AGENTROUTER_API_BASE: str = "https://agentrouter.org/v1"
    KITTY_DISABLE_AGENTROUTER: str = ""
    NVIDIA_CHAT_MODEL: str = "deepseek-ai/deepseek-v4-pro"
    NVIDIA_API_BASE: str = "https://integrate.api.nvidia.com/v1"

    # AgentRouter request headers (optional overrides)
    KITTY_AGENTROUTER_USER_AGENT: str = ""
    KITTY_AGENTROUTER_ORIGINATOR: str = ""
    KITTY_AGENTROUTER_VERSION: str = ""
    KITTY_AGENTROUTER_EXTRA_HEADERS_JSON: str = ""
    KITTY_AGENTROUTER_NO_ALT_UA_RETRY: str = ""


def get_settings() -> Settings:
    """Return a fresh Settings instance, re-reading os.environ each call.

    Do NOT cache — tests rely on monkeypatch.setenv taking effect immediately.
    """
    return Settings()
