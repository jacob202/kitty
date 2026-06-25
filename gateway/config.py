"""Central configuration for the gateway.

Lane D: this module is the single source of truth for runtime
configuration. Other modules should import from here instead of
calling ``os.environ.get`` directly. The migration is incremental;
existing ``os.environ.get`` call sites continue to work.

The pattern is:

- Top-of-file: env load (so .env is read once, at import time).
- Module-level constants for values that are known at import time
  and rarely change at runtime (host, port, paths).
- ``get_setting(name, default, cast)`` for values that should be
  re-read at call time (e.g. test overrides, runtime toggles).
- ``require_setting(name)`` for values that have no sensible default
  and must be set or the gateway should fail loud on first use.

Fail loud, not silent: ``require_setting`` raises ``ConfigError``
with a message that names the missing key and where to set it.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Callable, TypeVar

from dotenv import load_dotenv

from gateway.errors import ConfigError
from gateway.settings import get_settings

PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(PROJECT_ROOT / ".env")

T = TypeVar("T")

# Import-time host/port now flow through the validated Settings model so type
# coercion and defaults live in one place. The call-time get_setting/
# require_setting helpers below still serve values that must re-read os.environ
# (test overrides, runtime toggles).
_settings = get_settings()

# --- Gateway (process that this module is part of) ---

GATEWAY_HOST: str = _settings.GATEWAY_HOST
GATEWAY_PORT: int = _settings.GATEWAY_PORT
GATEWAY_BASE_URL: str = f"http://{GATEWAY_HOST}:{GATEWAY_PORT}"

# --- LiteLLM (separate proxy process) ---

LITELLM_HOST: str = _settings.LITELLM_HOST
LITELLM_PORT: int = _settings.LITELLM_PORT
LITELLM_BASE_URL: str = f"http://{LITELLM_HOST}:{LITELLM_PORT}"


# --- Required at request time, not import time ---

def require_setting(name: str) -> str:
    """Return the env var, or raise ConfigError if missing."""
    value = os.environ.get(name)
    if value is None or value == "":
        raise ConfigError(
            f"required setting {name!r} is not set",
            details={"key": name, "hint": f"set {name} in .env or your shell"},
        )
    return value


def get_setting(name: str, default: T, *, cast: Callable[[str], T] | None = None) -> T:
    """Return the env var, or ``default``. Re-read on each call.

    ``cast`` runs on the raw string before the default is used. If
    ``cast`` raises (e.g. ``int("abc")``), the call raises
    ``ConfigError`` with the parse failure wrapped.
    """
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    if cast is None:
        return raw  # type: ignore[return-value]
    try:
        return cast(raw)
    except (TypeError, ValueError) as exc:
        raise ConfigError(
            f"setting {name!r} could not be parsed",
            details={"key": name, "raw": raw, "parser": getattr(cast, "__name__", str(cast))},
        ) from exc


# --- Convenience accessors for the most common values ---

def gateway_secret() -> str:
    """Return the bearer token the gateway expects on protected routes."""
    return require_setting("GATEWAY_SECRET")


def litellm_key() -> str:
    """Return the LiteLLM master key (used for proxy auth when set)."""
    return require_setting("LITELLM_KEY")


def env_name() -> str:
    """Return the active environment name, defaulting to ``local``."""
    return get_setting("KITTY_ENV", "local")


def is_test_env() -> bool:
    """True when ``KITTY_ENV`` is ``test`` or starts with ``ci``."""
    name = env_name().lower()
    return name == "test" or name.startswith("ci") or name == "pytest"
