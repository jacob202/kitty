"""Unit tests for backend/router.py — classify, build_system_prompt, get_model, get_max_tokens."""
import os
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-for-router-tests")

import pytest


class TestClassify:
    """classify() must return the correct specialist based on keyword signals."""

    def test_coder_keyword_code(self):
        from backend.router import classify
        assert classify("can you write me some code?") == "coder"

    def test_coder_keyword_bug(self):
        from backend.router import classify
        assert classify("There is a bug in my function") == "coder"

    def test_coder_keyword_python(self):
        from backend.router import classify
        assert classify("Help me with python scripting") == "coder"

    def test_coder_keyword_debug(self):
        from backend.router import classify
        assert classify("debug this error for me") == "coder"

    def test_coder_keyword_sql(self):
        from backend.router import classify
        assert classify("write a SQL query for me") == "coder"

    def test_researcher_keyword_research(self):
        from backend.router import classify
        assert classify("research quantum computing for me") == "researcher"

    def test_researcher_keyword_what_is(self):
        from backend.router import classify
        assert classify("what is the capital of France?") == "researcher"

    def test_researcher_keyword_explain(self):
        from backend.router import classify
        assert classify("explain how photosynthesis works") == "researcher"

    def test_researcher_keyword_summarize(self):
        from backend.router import classify
        assert classify("summarize this paper for me") == "researcher"

    def test_creative_keyword_write(self):
        from backend.router import classify
        assert classify("write me a story about dragons") == "creative"

    def test_creative_keyword_poem(self):
        from backend.router import classify
        assert classify("write me a poem") == "creative"

    def test_creative_keyword_brainstorm(self):
        from backend.router import classify
        assert classify("let's brainstorm some ideas") == "creative"

    def test_creative_keyword_fiction(self):
        from backend.router import classify
        assert classify("I need fiction for my book") == "creative"

    def test_companion_keyword_feeling(self):
        from backend.router import classify
        assert classify("I am feeling really down today") == "companion"

    def test_companion_keyword_sad(self):
        from backend.router import classify
        assert classify("I feel so sad today") == "companion"

    def test_companion_keyword_lonely(self):
        from backend.router import classify
        assert classify("I'm so lonely these days") == "companion"

    def test_companion_keyword_vent(self):
        from backend.router import classify
        assert classify("I just need to vent about my day") == "companion"

    def test_analyst_keyword_should_i(self):
        from backend.router import classify
        assert classify("should i take this job offer?") == "analyst"

    def test_analyst_keyword_decision(self):
        from backend.router import classify
        assert classify("I need help with this decision") == "analyst"

    def test_analyst_keyword_analyze(self):
        from backend.router import classify
        assert classify("analyze the pros and cons for me") == "analyst"

    def test_analyst_keyword_strategy(self):
        from backend.router import classify
        assert classify("what is the best strategy here?") == "analyst"

    def test_general_fallback_empty_string(self):
        from backend.router import classify
        assert classify("") == "general"

    def test_general_fallback_no_keywords(self):
        from backend.router import classify
        assert classify("hello there") == "general"

    def test_general_fallback_gibberish(self):
        from backend.router import classify
        assert classify("xyzzy plugh") == "general"

    def test_case_insensitive_coder(self):
        from backend.router import classify
        assert classify("WRITE SOME CODE FOR ME") == "coder"

    def test_case_insensitive_researcher(self):
        from backend.router import classify
        assert classify("WHAT IS machine learning?") == "researcher"

    def test_highest_score_wins(self):
        """A message with multiple coder keywords must route to coder."""
        from backend.router import classify
        # "code bug function class debug" — 5 coder hits
        result = classify("I have a code bug in my function class, need to debug it")
        assert result == "coder"

    def test_tie_does_not_return_general(self):
        """When any specialist scores > 0, result must not be 'general'."""
        from backend.router import classify
        result = classify("write some code")  # both creative (write) and coder (code)
        assert result != "general"


class TestLoad:
    """_load() must return file contents or empty string for missing files."""

    def test_load_existing_file(self, tmp_path):
        from backend.router import _load
        f = tmp_path / "test.md"
        f.write_text("hello world", encoding="utf-8")
        assert _load(f) == "hello world"

    def test_load_missing_file_returns_empty_string(self, tmp_path):
        from backend.router import _load
        missing = tmp_path / "nonexistent.md"
        assert _load(missing) == ""

    def test_load_empty_file(self, tmp_path):
        from backend.router import _load
        f = tmp_path / "empty.md"
        f.write_text("", encoding="utf-8")
        assert _load(f) == ""

    def test_load_unicode_content(self, tmp_path):
        from backend.router import _load
        f = tmp_path / "unicode.md"
        f.write_text("héllo wörld 🐱", encoding="utf-8")
        assert _load(f) == "héllo wörld 🐱"


class TestBuildSystemPrompt:
    """build_system_prompt() must assemble sections with --- separators."""

    def test_soul_only_when_no_extension_no_blocks(self):
        """With general specialist and no blocks, only soul content is returned."""
        from backend.router import build_system_prompt
        with patch("backend.router._load") as mock_load:
            mock_load.side_effect = lambda p: "SOUL" if "kitty.md" in str(p) else ""
            result = build_system_prompt("general", memory_block="", profile_block="")
        assert result == "SOUL"

    def test_includes_specialist_extension(self):
        """A known specialist's file content is appended after the soul."""
        from backend.router import build_system_prompt, SOUL_FILE, SPECIALISTS
        with patch("backend.router._load") as mock_load:
            def _side_effect(p):
                if p == SOUL_FILE:
                    return "SOUL"
                if "coder.md" in str(p):
                    return "CODER_EXT"
                return ""
            mock_load.side_effect = _side_effect
            result = build_system_prompt("coder", memory_block="", profile_block="")
        assert "SOUL" in result
        assert "CODER_EXT" in result
        assert result.index("SOUL") < result.index("CODER_EXT")

    def test_sections_joined_by_separator(self):
        """Sections must be joined by '\\n\\n---\\n\\n'."""
        from backend.router import build_system_prompt
        with patch("backend.router._load") as mock_load:
            mock_load.side_effect = lambda p: "SOUL" if "kitty.md" in str(p) else "EXT"
            result = build_system_prompt("coder", memory_block="", profile_block="")
        assert "\n\n---\n\n" in result

    def test_profile_block_appended_when_present(self):
        """profile_block is included in output when non-empty."""
        from backend.router import build_system_prompt
        with patch("backend.router._load") as mock_load:
            mock_load.return_value = "SOUL"
            result = build_system_prompt("general", memory_block="", profile_block="PROFILE")
        assert "PROFILE" in result

    def test_memory_block_appended_when_present(self):
        """memory_block is included in output when non-empty."""
        from backend.router import build_system_prompt
        with patch("backend.router._load") as mock_load:
            mock_load.return_value = "SOUL"
            result = build_system_prompt("general", memory_block="MEMORIES", profile_block="")
        assert "MEMORIES" in result

    def test_profile_before_memory(self):
        """profile_block appears before memory_block in the assembled prompt."""
        from backend.router import build_system_prompt
        with patch("backend.router._load") as mock_load:
            mock_load.return_value = "SOUL"
            result = build_system_prompt(
                "general", memory_block="MEMORIES", profile_block="PROFILE"
            )
        assert result.index("PROFILE") < result.index("MEMORIES")

    def test_empty_profile_and_memory_excluded(self):
        """Empty profile_block and memory_block must not add extra separators."""
        from backend.router import build_system_prompt
        with patch("backend.router._load") as mock_load:
            mock_load.return_value = "SOUL"
            result = build_system_prompt("general", memory_block="", profile_block="")
        # Should be exactly "SOUL" with no trailing separators
        assert result == "SOUL"

    def test_unknown_specialist_no_extension(self):
        """An unknown specialist name produces no extension section."""
        from backend.router import build_system_prompt
        with patch("backend.router._load") as mock_load:
            mock_load.return_value = "SOUL"
            result = build_system_prompt("unknown_specialist", memory_block="", profile_block="")
        assert result == "SOUL"


class TestGetModel:
    """get_model() must return the correct model string per specialist."""

    def test_coder_uses_opus(self):
        from backend.router import get_model
        from backend.config import settings
        assert get_model("coder") == settings.opus_model

    def test_analyst_uses_opus(self):
        from backend.router import get_model
        from backend.config import settings
        assert get_model("analyst") == settings.opus_model

    def test_researcher_uses_sonnet(self):
        from backend.router import get_model
        from backend.config import settings
        assert get_model("researcher") == settings.sonnet_model

    def test_creative_uses_sonnet(self):
        from backend.router import get_model
        from backend.config import settings
        assert get_model("creative") == settings.sonnet_model

    def test_companion_uses_sonnet(self):
        from backend.router import get_model
        from backend.config import settings
        assert get_model("companion") == settings.sonnet_model

    def test_general_uses_sonnet(self):
        from backend.router import get_model
        from backend.config import settings
        assert get_model("general") == settings.sonnet_model

    def test_unknown_specialist_falls_back_to_sonnet(self):
        from backend.router import get_model
        from backend.config import settings
        assert get_model("does_not_exist") == settings.sonnet_model


class TestGetMaxTokens:
    """get_max_tokens() must return the correct token budget per specialist."""

    def test_coder_uses_opus_max_tokens(self):
        from backend.router import get_max_tokens
        from backend.config import settings
        assert get_max_tokens("coder") == settings.opus_max_tokens

    def test_analyst_uses_opus_max_tokens(self):
        from backend.router import get_max_tokens
        from backend.config import settings
        assert get_max_tokens("analyst") == settings.opus_max_tokens

    def test_researcher_uses_sonnet_max_tokens(self):
        from backend.router import get_max_tokens
        from backend.config import settings
        assert get_max_tokens("researcher") == settings.sonnet_max_tokens

    def test_creative_uses_sonnet_max_tokens(self):
        from backend.router import get_max_tokens
        from backend.config import settings
        assert get_max_tokens("creative") == settings.sonnet_max_tokens

    def test_companion_uses_sonnet_max_tokens(self):
        from backend.router import get_max_tokens
        from backend.config import settings
        assert get_max_tokens("companion") == settings.sonnet_max_tokens

    def test_general_uses_sonnet_max_tokens(self):
        from backend.router import get_max_tokens
        from backend.config import settings
        assert get_max_tokens("general") == settings.sonnet_max_tokens

    def test_unknown_specialist_falls_back_to_sonnet_max_tokens(self):
        from backend.router import get_max_tokens
        from backend.config import settings
        assert get_max_tokens("does_not_exist") == settings.sonnet_max_tokens

    def test_max_tokens_are_positive_integers(self):
        """All specialist token budgets must be positive integers."""
        from backend.router import get_max_tokens
        for specialist in ["coder", "analyst", "researcher", "creative", "companion", "general"]:
            tokens = get_max_tokens(specialist)
            assert isinstance(tokens, int)
            assert tokens > 0
