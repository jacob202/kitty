"""Tests for skill_registry — discover, get, search, invoke."""

from gateway.skill_registry import (
    _yaml_frontmatter,
    discover,
    get,
    invoke,
    search,
)


class TestYamlFrontmatter:
    def test_parses_simple_fields(self):
        text = "---\nname: test-skill\ndescription: does stuff\n---\n\n# Body here"
        result = _yaml_frontmatter(text)
        assert result["name"] == "test-skill"
        assert result["description"] == "does stuff"

    def test_empty_for_no_frontmatter(self):
        assert _yaml_frontmatter("# Just markdown") == {}

    def test_parses_list_field(self):
        text = '---\nname: test\nallowed_tools: [bash, read, write]\n---\n\nBody'
        result = _yaml_frontmatter(text)
        assert result["allowed_tools"] == ["bash", "read", "write"]

    def test_parses_when_to_use(self):
        text = "---\nname: test\ndescription: desc\nwhen_to_use: for complex tasks\n---\n\nBody"
        result = _yaml_frontmatter(text)
        assert result["when_to_use"] == "for complex tasks"


class TestDiscover:
    def test_discovers_skills(self):
        skills = discover()
        assert len(skills) >= 1
        names = {s["name"] for s in skills}
        assert "journal-entry" in names

    def test_discover_cache(self):
        s1 = discover()
        s2 = discover()
        assert s1 == s2  # same content from cache

    def test_discover_force_refresh(self):
        discover()
        s2 = discover(force_refresh=True)
        assert len(s2) >= 1

    def test_archived_skills_are_not_active(self):
        names = {s["name"] for s in discover(force_refresh=True)}
        assert "red-team" not in names
        assert "root-cause-analysis" not in names

    def test_only_top_level_archive_namespace_is_excluded(self, tmp_path, monkeypatch):
        import gateway.skill_registry as registry

        root = tmp_path / "skills"
        top_archive = root / "_archive" / "retired"
        nested_archive = root / "engineering" / "_archive"
        top_archive.mkdir(parents=True)
        nested_archive.mkdir(parents=True)
        top_archive.joinpath("SKILL.md").write_text(
            "---\nname: retired\ndescription: retired skill\n---\n"
        )
        nested_archive.joinpath("SKILL.md").write_text(
            "---\nname: nested-active\ndescription: active nested skill\n---\n"
        )

        monkeypatch.setattr(registry, "SKILL_ROOTS", [root])
        monkeypatch.setattr(registry, "_registry", None)
        names = {skill["name"] for skill in registry.discover(force_refresh=True)}
        assert "retired" not in names
        assert "nested-active" in names


class TestGet:
    def test_get_existing(self):
        skill = get("journal-entry")
        assert skill is not None
        assert "description" in skill

    def test_get_nonexistent(self):
        assert get("nonexistent-skill") is None


class TestSearch:
    def test_search_by_name(self):
        results = search("journal")
        assert len(results) >= 1

    def test_search_empty_returns_all(self):
        results = search("")
        assert len(results) >= 1

    def test_search_no_match(self):
        results = search("xyznonexistent123")
        assert results == []


class TestInvoke:
    def test_invoke_returns_prompt(self):
        result = invoke("journal-entry")
        assert "error" not in result
        assert "prompt" in result
        assert len(result["prompt"]) > 0

    def test_invoke_with_context(self):
        result = invoke("journal-entry", context="test context")
        assert "test context" in result["prompt"]

    def test_invoke_nonexistent(self):
        result = invoke("nonexistent")
        assert "error" in result
