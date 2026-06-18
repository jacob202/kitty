"""Unit tests for backend/config.py — Settings class and SOUL_DIR constant."""
import os
import sys
from pathlib import Path

# Must set ANTHROPIC_API_KEY before importing backend modules, because
# `settings = Settings()` runs at module import time.
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-for-config-tests")

import pytest
from pydantic import ValidationError


class TestSoulDir:
    """SOUL_DIR should point at the repo-level 'soul/' directory."""

    def test_soul_dir_is_path_object(self):
        """SOUL_DIR must be a Path instance."""
        from backend.config import SOUL_DIR
        assert isinstance(SOUL_DIR, Path)

    def test_soul_dir_name(self):
        """SOUL_DIR must be named 'soul'."""
        from backend.config import SOUL_DIR
        assert SOUL_DIR.name == "soul"

    def test_soul_dir_parent_is_repo_root(self):
        """SOUL_DIR must live one level below the repository root."""
        from backend.config import SOUL_DIR
        repo_root = Path(__file__).resolve().parent.parent
        assert SOUL_DIR == repo_root / "soul"


class TestSettingsDefaults:
    """Settings should expose correct default values for optional fields."""

    def test_mem0_api_key_defaults_to_empty_string(self):
        """mem0_api_key defaults to '' when not set in environment."""
        from backend.config import Settings
        s = Settings(anthropic_api_key="sk-test")
        assert s.mem0_api_key == ""

    def test_user_id_defaults_to_default(self):
        """user_id defaults to 'default' when USER_ID env var is absent."""
        from backend.config import Settings
        s = Settings(anthropic_api_key="sk-test")
        assert s.user_id == "default"

    def test_haiku_model_default(self):
        """haiku_model has the expected default value."""
        from backend.config import Settings
        s = Settings(anthropic_api_key="sk-test")
        assert s.haiku_model == "claude-haiku-4-5-20251001"

    def test_sonnet_model_default(self):
        """sonnet_model has the expected default value."""
        from backend.config import Settings
        s = Settings(anthropic_api_key="sk-test")
        assert s.sonnet_model == "claude-sonnet-4-6"

    def test_opus_model_default(self):
        """opus_model has the expected default value."""
        from backend.config import Settings
        s = Settings(anthropic_api_key="sk-test")
        assert s.opus_model == "claude-opus-4-7"

    def test_haiku_max_tokens_default(self):
        """haiku_max_tokens defaults to 1024."""
        from backend.config import Settings
        s = Settings(anthropic_api_key="sk-test")
        assert s.haiku_max_tokens == 1024

    def test_sonnet_max_tokens_default(self):
        """sonnet_max_tokens defaults to 4096."""
        from backend.config import Settings
        s = Settings(anthropic_api_key="sk-test")
        assert s.sonnet_max_tokens == 4096

    def test_opus_max_tokens_default(self):
        """opus_max_tokens defaults to 8192."""
        from backend.config import Settings
        s = Settings(anthropic_api_key="sk-test")
        assert s.opus_max_tokens == 8192


class TestSettingsValidation:
    """Settings validator must reject blank or missing ANTHROPIC_API_KEY."""

    def test_valid_api_key_accepted(self):
        """A non-empty API key must be accepted without error."""
        from backend.config import Settings
        s = Settings(anthropic_api_key="sk-ant-valid-key")
        assert s.anthropic_api_key == "sk-ant-valid-key"

    def test_empty_api_key_raises(self):
        """An empty ANTHROPIC_API_KEY must raise a ValidationError."""
        from backend.config import Settings
        with pytest.raises(ValidationError):
            Settings(anthropic_api_key="")

    def test_whitespace_only_api_key_raises(self):
        """A whitespace-only ANTHROPIC_API_KEY must raise a ValidationError."""
        from backend.config import Settings
        with pytest.raises(ValidationError):
            Settings(anthropic_api_key="   ")

    def test_key_with_leading_trailing_whitespace_is_accepted(self):
        """Pydantic does not strip the key; a key with surrounding spaces is valid
        as long as it has non-whitespace content (the validator only strips for check)."""
        from backend.config import Settings
        # The validator calls v.strip() for the emptiness check but returns original v.
        s = Settings(anthropic_api_key="  sk-padded  ")
        assert s.anthropic_api_key == "  sk-padded  "

    def test_settings_singleton_has_valid_key(self):
        """The module-level 'settings' object must have a non-empty API key."""
        from backend.config import settings
        assert settings.anthropic_api_key.strip() != ""

    def test_env_override_user_id(self, monkeypatch):
        """user_id can be overridden via the USER_ID environment variable."""
        from backend.config import Settings
        monkeypatch.setenv("USER_ID", "alice")
        s = Settings(anthropic_api_key="sk-test")
        assert s.user_id == "alice"

    def test_env_override_mem0_api_key(self, monkeypatch):
        """mem0_api_key can be set via the MEM0_API_KEY environment variable."""
        from backend.config import Settings
        monkeypatch.setenv("MEM0_API_KEY", "m0-key-xyz")
        s = Settings(anthropic_api_key="sk-test")
        assert s.mem0_api_key == "m0-key-xyz"