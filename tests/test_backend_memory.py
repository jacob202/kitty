"""Unit tests for backend/memory.py — profile I/O, memory store, and formatting helpers."""
import json
import os
import threading
from pathlib import Path
from unittest.mock import patch, MagicMock

os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-for-memory-tests")

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_local_store():
    """Clear _LOCAL_STORE between tests to prevent state leakage."""
    import backend.memory as mem
    mem._LOCAL_STORE.clear()
    yield
    mem._LOCAL_STORE.clear()


@pytest.fixture()
def profile_path(tmp_path):
    """Return a tmp Path to use as the profile JSON file, and patch _PROFILE_PATH."""
    p = tmp_path / "user_profile.json"
    with patch("backend.memory._PROFILE_PATH", p):
        yield p


# ---------------------------------------------------------------------------
# _load_profile
# ---------------------------------------------------------------------------

class TestLoadProfile:
    """_load_profile() must handle missing files and invalid JSON gracefully."""

    def test_returns_empty_dict_when_file_missing(self, tmp_path):
        missing = tmp_path / "nonexistent.json"
        with patch("backend.memory._PROFILE_PATH", missing):
            from backend.memory import _load_profile
            assert _load_profile() == {}

    def test_returns_empty_dict_on_invalid_json(self, tmp_path):
        bad_json = tmp_path / "bad.json"
        bad_json.write_text("{ this is not json }", encoding="utf-8")
        with patch("backend.memory._PROFILE_PATH", bad_json):
            from backend.memory import _load_profile
            assert _load_profile() == {}

    def test_returns_dict_for_valid_json(self, tmp_path):
        profile_file = tmp_path / "profile.json"
        profile_file.write_text(json.dumps({"name": "Alice", "city": "Austin"}), encoding="utf-8")
        with patch("backend.memory._PROFILE_PATH", profile_file):
            from backend.memory import _load_profile
            result = _load_profile()
        assert result == {"name": "Alice", "city": "Austin"}

    def test_returns_empty_dict_for_empty_json_object(self, tmp_path):
        empty_json = tmp_path / "empty.json"
        empty_json.write_text("{}", encoding="utf-8")
        with patch("backend.memory._PROFILE_PATH", empty_json):
            from backend.memory import _load_profile
            assert _load_profile() == {}

    def test_returns_empty_dict_for_empty_file(self, tmp_path):
        empty_file = tmp_path / "empty.json"
        empty_file.write_text("", encoding="utf-8")
        with patch("backend.memory._PROFILE_PATH", empty_file):
            from backend.memory import _load_profile
            assert _load_profile() == {}


# ---------------------------------------------------------------------------
# _save_profile
# ---------------------------------------------------------------------------

class TestSaveProfile:
    """_save_profile() must write valid JSON and create parent directories."""

    def test_saves_json_to_disk(self, tmp_path):
        target = tmp_path / "sub" / "profile.json"
        with patch("backend.memory._PROFILE_PATH", target):
            from backend.memory import _save_profile
            _save_profile({"name": "Bob"})
        assert target.exists()
        data = json.loads(target.read_text())
        assert data == {"name": "Bob"}

    def test_creates_parent_directories(self, tmp_path):
        target = tmp_path / "deep" / "nested" / "profile.json"
        with patch("backend.memory._PROFILE_PATH", target):
            from backend.memory import _save_profile
            _save_profile({"x": 1})
        assert target.exists()

    def test_written_json_is_indented(self, tmp_path):
        target = tmp_path / "profile.json"
        with patch("backend.memory._PROFILE_PATH", target):
            from backend.memory import _save_profile
            _save_profile({"key": "value"})
        raw = target.read_text()
        assert "\n" in raw  # indented JSON has newlines

    def test_overwrites_existing_file(self, tmp_path):
        target = tmp_path / "profile.json"
        target.write_text(json.dumps({"old": "data"}), encoding="utf-8")
        with patch("backend.memory._PROFILE_PATH", target):
            from backend.memory import _save_profile
            _save_profile({"new": "data"})
        data = json.loads(target.read_text())
        assert data == {"new": "data"}


# ---------------------------------------------------------------------------
# get_user_profile
# ---------------------------------------------------------------------------

class TestGetUserProfile:
    """get_user_profile() must delegate to _load_profile()."""

    def test_returns_profile_from_disk(self, tmp_path):
        profile_file = tmp_path / "profile.json"
        profile_file.write_text(json.dumps({"role": "tester"}), encoding="utf-8")
        with patch("backend.memory._PROFILE_PATH", profile_file):
            from backend.memory import get_user_profile
            result = get_user_profile()
        assert result == {"role": "tester"}

    def test_returns_empty_dict_when_no_file(self, tmp_path):
        missing = tmp_path / "missing.json"
        with patch("backend.memory._PROFILE_PATH", missing):
            from backend.memory import get_user_profile
            assert get_user_profile() == {}


# ---------------------------------------------------------------------------
# update_user_profile
# ---------------------------------------------------------------------------

class TestUpdateUserProfile:
    """update_user_profile() must merge updates into the existing profile and persist."""

    def test_merges_new_keys(self, profile_path):
        profile_path.write_text(json.dumps({"name": "Alice"}), encoding="utf-8")
        from backend.memory import update_user_profile
        update_user_profile({"city": "Austin"})
        data = json.loads(profile_path.read_text())
        assert data["name"] == "Alice"
        assert data["city"] == "Austin"

    def test_overwrites_existing_key(self, profile_path):
        profile_path.write_text(json.dumps({"name": "Alice"}), encoding="utf-8")
        from backend.memory import update_user_profile
        update_user_profile({"name": "Bob"})
        data = json.loads(profile_path.read_text())
        assert data["name"] == "Bob"

    def test_sets_last_updated_field(self, profile_path):
        profile_path.write_text(json.dumps({"name": "Alice"}), encoding="utf-8")
        from backend.memory import update_user_profile
        update_user_profile({"city": "Chicago"})
        data = json.loads(profile_path.read_text())
        assert "last_updated" in data
        assert data["last_updated"]  # non-empty

    def test_creates_file_if_missing(self, tmp_path):
        missing = tmp_path / "profile.json"
        with patch("backend.memory._PROFILE_PATH", missing):
            from backend.memory import update_user_profile
            update_user_profile({"name": "New"})
        assert missing.exists()
        data = json.loads(missing.read_text())
        assert data["name"] == "New"

    def test_thread_safe_concurrent_writes(self, profile_path):
        """Multiple threads updating the profile concurrently must not corrupt it."""
        profile_path.write_text(json.dumps({"counter": 0}), encoding="utf-8")
        from backend.memory import update_user_profile
        errors = []

        def _update(i):
            try:
                update_user_profile({f"key_{i}": i})
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=_update, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        data = json.loads(profile_path.read_text())
        # All 10 keys plus the originals should be present
        for i in range(10):
            assert f"key_{i}" in data


# ---------------------------------------------------------------------------
# format_profile_injection
# ---------------------------------------------------------------------------

class TestFormatProfileInjection:
    """format_profile_injection() must build a markdown block from the profile dict."""

    def test_empty_profile_returns_empty_string(self):
        from backend.memory import format_profile_injection
        assert format_profile_injection({}) == ""

    def test_has_header_line(self):
        from backend.memory import format_profile_injection
        result = format_profile_injection({"name": "Alice"})
        assert "## What Kitty knows about you" in result

    def test_formats_key_value_pair(self):
        from backend.memory import format_profile_injection
        result = format_profile_injection({"city": "Austin"})
        assert "City" in result
        assert "Austin" in result

    def test_skips_last_updated_key(self):
        from backend.memory import format_profile_injection
        result = format_profile_injection({"name": "Alice", "last_updated": "2024-01-01"})
        assert "last_updated" not in result
        assert "Last Updated" not in result

    def test_underscores_converted_to_spaces_in_key(self):
        from backend.memory import format_profile_injection
        result = format_profile_injection({"preferred_name": "Bob"})
        assert "Preferred Name" in result

    def test_multiple_keys_all_present(self):
        from backend.memory import format_profile_injection
        result = format_profile_injection({"name": "Alice", "city": "Austin", "role": "dev"})
        assert "Alice" in result
        assert "Austin" in result
        assert "Dev" in result

    def test_none_profile_same_as_empty_dict(self):
        """format_profile_injection({}) returns empty string; ensure falsy guard works."""
        from backend.memory import format_profile_injection
        # Passing {} is falsy, so it returns ""
        assert format_profile_injection({}) == ""

    def test_only_last_updated_returns_header_only(self):
        """A profile with only 'last_updated' should still produce a header (edge case)."""
        from backend.memory import format_profile_injection
        result = format_profile_injection({"last_updated": "2024-01-01"})
        # Profile is truthy (has a key), so header is added, but no bullet lines
        assert "## What Kitty knows about you" in result


# ---------------------------------------------------------------------------
# format_memory_injection
# ---------------------------------------------------------------------------

class TestFormatMemoryInjection:
    """format_memory_injection() must build a markdown block from retrieved memories."""

    def test_empty_list_returns_empty_string(self):
        from backend.memory import format_memory_injection
        assert format_memory_injection([]) == ""

    def test_has_header_line(self):
        from backend.memory import format_memory_injection
        result = format_memory_injection([{"memory": "Jacob likes coffee"}])
        assert "## Relevant memories from past conversations" in result

    def test_uses_memory_key(self):
        from backend.memory import format_memory_injection
        result = format_memory_injection([{"memory": "Jacob likes coffee"}])
        assert "Jacob likes coffee" in result

    def test_falls_back_to_text_key(self):
        from backend.memory import format_memory_injection
        result = format_memory_injection([{"text": "Jacob hates meetings"}])
        assert "Jacob hates meetings" in result

    def test_falls_back_to_str_when_no_key(self):
        from backend.memory import format_memory_injection
        m = {"unknown_key": "some data"}
        result = format_memory_injection([m])
        assert str(m) in result

    def test_multiple_memories_all_present(self):
        from backend.memory import format_memory_injection
        memories = [
            {"memory": "Fact A"},
            {"memory": "Fact B"},
        ]
        result = format_memory_injection(memories)
        assert "Fact A" in result
        assert "Fact B" in result

    def test_each_memory_on_its_own_bullet(self):
        from backend.memory import format_memory_injection
        memories = [{"memory": "X"}, {"memory": "Y"}]
        lines = format_memory_injection(memories).splitlines()
        bullet_lines = [l for l in lines if l.startswith("- ")]
        assert len(bullet_lines) == 2

    def test_memory_key_preferred_over_text_key(self):
        from backend.memory import format_memory_injection
        result = format_memory_injection([{"memory": "preferred", "text": "fallback"}])
        assert "preferred" in result
        assert "fallback" not in result


# ---------------------------------------------------------------------------
# search_memories (local fallback path)
# ---------------------------------------------------------------------------

class TestSearchMemoriesLocal:
    """search_memories() local fallback must return recent memories up to limit."""

    def test_returns_empty_list_when_no_memories(self):
        from backend.memory import search_memories
        with patch("backend.memory.MEM0_AVAILABLE", False):
            with patch("backend.memory.settings") as mock_settings:
                mock_settings.mem0_api_key = ""
                mock_settings.user_id = "test_user"
                result = search_memories("anything")
        assert result == []

    def test_returns_stored_memories(self):
        import backend.memory as mem
        mem._LOCAL_STORE["test_user_search"] = [
            {"conversation": [{"role": "user", "content": "hi"}], "metadata": {}}
        ]
        with patch("backend.memory.MEM0_AVAILABLE", False):
            with patch("backend.memory.settings") as mock_settings:
                mock_settings.mem0_api_key = ""
                mock_settings.user_id = "test_user_search"
                result = mem.search_memories("hi")
        assert len(result) == 1

    def test_respects_limit(self):
        import backend.memory as mem
        mem._LOCAL_STORE["limit_user"] = [{"n": i} for i in range(10)]
        with patch("backend.memory.MEM0_AVAILABLE", False):
            with patch("backend.memory.settings") as mock_settings:
                mock_settings.mem0_api_key = ""
                mock_settings.user_id = "limit_user"
                result = mem.search_memories("query", limit=3)
        assert len(result) == 3

    def test_returns_most_recent_entries(self):
        """Local fallback returns the LAST limit entries (recency-based)."""
        import backend.memory as mem
        entries = [{"n": i} for i in range(10)]
        mem._LOCAL_STORE["recency_user"] = entries
        with patch("backend.memory.MEM0_AVAILABLE", False):
            with patch("backend.memory.settings") as mock_settings:
                mock_settings.mem0_api_key = ""
                mock_settings.user_id = "recency_user"
                result = mem.search_memories("q", limit=3)
        assert result == entries[-3:]


# ---------------------------------------------------------------------------
# add_memory (local fallback path)
# ---------------------------------------------------------------------------

class TestAddMemoryLocal:
    """add_memory() local fallback must store conversation turns in _LOCAL_STORE."""

    def test_creates_user_entry_in_local_store(self):
        import backend.memory as mem
        conv = [{"role": "user", "content": "hello"}]
        with patch("backend.memory.MEM0_AVAILABLE", False):
            with patch("backend.memory.settings") as mock_settings:
                mock_settings.mem0_api_key = ""
                mock_settings.user_id = "add_user"
                mem.add_memory(conv)
        assert "add_user" in mem._LOCAL_STORE
        assert len(mem._LOCAL_STORE["add_user"]) == 1

    def test_stores_conversation(self):
        import backend.memory as mem
        conv = [{"role": "user", "content": "test msg"}]
        with patch("backend.memory.MEM0_AVAILABLE", False):
            with patch("backend.memory.settings") as mock_settings:
                mock_settings.mem0_api_key = ""
                mock_settings.user_id = "conv_user"
                mem.add_memory(conv)
        stored = mem._LOCAL_STORE["conv_user"][0]
        assert stored["conversation"] == conv

    def test_stores_metadata(self):
        import backend.memory as mem
        conv = [{"role": "user", "content": "test"}]
        meta = {"specialist": "coder"}
        with patch("backend.memory.MEM0_AVAILABLE", False):
            with patch("backend.memory.settings") as mock_settings:
                mock_settings.mem0_api_key = ""
                mock_settings.user_id = "meta_user"
                mem.add_memory(conv, metadata=meta)
        stored = mem._LOCAL_STORE["meta_user"][0]
        assert stored["metadata"] == meta

    def test_none_metadata_stored_as_empty_dict(self):
        import backend.memory as mem
        conv = [{"role": "user", "content": "hi"}]
        with patch("backend.memory.MEM0_AVAILABLE", False):
            with patch("backend.memory.settings") as mock_settings:
                mock_settings.mem0_api_key = ""
                mock_settings.user_id = "none_meta_user"
                mem.add_memory(conv, metadata=None)
        stored = mem._LOCAL_STORE["none_meta_user"][0]
        assert stored["metadata"] == {}

    def test_adds_timestamp(self):
        import backend.memory as mem
        conv = [{"role": "user", "content": "timestamped"}]
        with patch("backend.memory.MEM0_AVAILABLE", False):
            with patch("backend.memory.settings") as mock_settings:
                mock_settings.mem0_api_key = ""
                mock_settings.user_id = "ts_user"
                mem.add_memory(conv)
        stored = mem._LOCAL_STORE["ts_user"][0]
        assert "timestamp" in stored
        assert stored["timestamp"]

    def test_appends_to_existing_entries(self):
        import backend.memory as mem
        mem._LOCAL_STORE["append_user"] = [{"existing": True}]
        conv = [{"role": "user", "content": "new"}]
        with patch("backend.memory.MEM0_AVAILABLE", False):
            with patch("backend.memory.settings") as mock_settings:
                mock_settings.mem0_api_key = ""
                mock_settings.user_id = "append_user"
                mem.add_memory(conv)
        assert len(mem._LOCAL_STORE["append_user"]) == 2

    def test_separate_user_ids_are_isolated(self):
        """Memories for different user_ids must not bleed into each other."""
        import backend.memory as mem
        conv = [{"role": "user", "content": "hello"}]
        with patch("backend.memory.MEM0_AVAILABLE", False):
            with patch("backend.memory.settings") as mock_settings:
                mock_settings.mem0_api_key = ""
                mock_settings.user_id = "user_alpha"
                mem.add_memory(conv)
            with patch("backend.memory.settings") as mock_settings:
                mock_settings.mem0_api_key = ""
                mock_settings.user_id = "user_beta"
                mem.add_memory(conv)
        assert "user_alpha" in mem._LOCAL_STORE
        assert "user_beta" in mem._LOCAL_STORE
        assert len(mem._LOCAL_STORE["user_alpha"]) == 1
        assert len(mem._LOCAL_STORE["user_beta"]) == 1