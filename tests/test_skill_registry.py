"""Tests for skill_registry — discover, get, search, invoke."""

from gateway.skill_registry import (
    _parse_skill_file,
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

    def test_parses_block_list(self):
        text = "---\nname: test\nallowed_tools:\n  - bash\n  - read\n---\n\nBody"
        result = _yaml_frontmatter(text)
        assert result["allowed_tools"] == ["bash", "read"]

    def test_parses_nested_metadata(self):
        text = (
            "---\nname: test\nmetadata:\n  author: jacob\n  tags: [a, b]\n---\n\nBody"
        )
        result = _yaml_frontmatter(text)
        assert result["metadata"] == {"author": "jacob", "tags": ["a", "b"]}

    def test_accepts_spec_hyphenated_allowed_tools(self):
        text = "---\nname: test\nallowed-tools: [bash, read]\n---\n\nBody"
        result = _yaml_frontmatter(text)
        assert result["allowed_tools"] == ["bash", "read"]
        assert "allowed-tools" not in result

    def test_falls_back_on_invalid_yaml(self):
        """An unquoted colon mid-value is invalid YAML but was tolerated by
        Kitty's original line parser — don't drop the skill over it."""
        text = "---\nname: test\ndescription: USE WHEN: doing a thing\n---\n\nBody"
        result = _yaml_frontmatter(text)
        assert result["name"] == "test"
        assert result["description"] == "USE WHEN: doing a thing"

    def test_parses_license_and_compatibility(self):
        text = "---\nname: test\nlicense: MIT\ncompatibility: claude\n---\n\nBody"
        result = _yaml_frontmatter(text)
        assert result["license"] == "MIT"
        assert result["compatibility"] == "claude"


class TestParseSkillFile:
    """Real YAML can yield non-string values where Kitty's fields expect
    text; _parse_skill_file must coerce or drop them, not crash or pass a
    bomb-shaped value through to callers like the /api/skills route."""

    def test_bare_description_coerces_to_empty_string(self, tmp_path):
        path = tmp_path / "SKILL.md"
        path.write_text("---\nname: test\ndescription:\n---\n\nBody")
        result = _parse_skill_file(path)
        assert result["description"] == ""

    def test_boolean_description_coerces_to_empty_string(self, tmp_path):
        path = tmp_path / "SKILL.md"
        path.write_text("---\nname: test\ndescription: yes\n---\n\nBody")
        result = _parse_skill_file(path)
        assert result["description"] == ""

    def test_non_string_name_is_rejected(self, tmp_path):
        path = tmp_path / "SKILL.md"
        path.write_text("---\nname: yes\n---\n\nBody")
        assert _parse_skill_file(path) is None

    def test_non_list_allowed_tools_coerces_to_empty_list(self, tmp_path):
        path = tmp_path / "SKILL.md"
        path.write_text("---\nname: test\nallowed_tools: not-a-list\n---\n\nBody")
        result = _parse_skill_file(path)
        assert result["allowed_tools"] == []

    def test_chat_launchable_is_explicit_boolean_metadata(self, tmp_path):
        path = tmp_path / "SKILL.md"
        path.write_text("---\nname: test\nchat_launchable: true\n---\n\nBody")
        result = _parse_skill_file(path)
        assert result["chat_launchable"] is True

    def test_chat_launchable_defaults_false_for_unmarked_skills(self, tmp_path):
        path = tmp_path / "SKILL.md"
        path.write_text("---\nname: test\n---\n\nBody")
        result = _parse_skill_file(path)
        assert result["chat_launchable"] is False

    def test_metadata_is_not_propagated(self, tmp_path):
        """metadata is spec-legal arbitrary YAML; passing it through let a
        few anchors/aliases turn a few hundred bytes into tens of megabytes
        on JSON serialization at /api/skills. Nothing consumes it today, so
        it is dropped rather than bounded."""
        path = tmp_path / "SKILL.md"
        path.write_text("---\nname: test\nmetadata:\n  author: jacob\n---\n\nBody")
        result = _parse_skill_file(path)
        assert "metadata" not in result

    def test_search_and_suggest_survive_non_string_description(self, tmp_path, monkeypatch):
        import gateway.skill_registry as registry

        root = tmp_path / "skills"
        root.mkdir()
        (root / "SKILL.md").write_text("---\nname: bare-desc\ndescription:\n---\n\nBody")

        monkeypatch.setattr(registry, "SKILL_ROOTS", [root])
        monkeypatch.setattr(registry, "_registry", None)
        # Must not raise (old code called .lower() on the raw frontmatter value).
        assert registry.search("anything") is not None
        assert registry.suggest("anything") == []


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
