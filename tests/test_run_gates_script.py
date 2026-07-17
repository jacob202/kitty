"""
Gate contract tests — verify that the project's required files and structural
invariants are in place. These run in CI with only pytest installed (no gateway deps).
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class TestRequiredFiles:
    """Core files that must always exist."""

    def test_gateway_app_present(self):
        """gateway/app.py must exist."""
        assert (ROOT / "gateway" / "app.py").exists()

    def test_gateway_paths_present(self):
        """gateway/paths.py must exist."""
        assert (ROOT / "gateway" / "paths.py").exists()

    def test_soul_file_present(self):
        """config/SOUL.md is Kitty's core identity file and must always exist."""
        assert (ROOT / "config" / "SOUL.md").exists(), "config/SOUL.md is Kitty's soul — it must exist"

    def test_active_continuity_files_present(self):
        """The active mission, authority map, and current checkpoints must exist."""
        required = [
            ROOT / "docs" / "ACTIVE_MISSION.md",
            ROOT / "docs" / "AUTHORITY_MAP.md",
            ROOT / ".claude" / "STATE.md",
            ROOT / ".claude" / "HANDOFF.md",
        ]
        assert all(path.exists() for path in required), required

    def test_env_example_present(self):
        """.env.example must exist to document required secrets."""
        assert (ROOT / ".env.example").exists()

    def test_claude_md_present(self):
        """CLAUDE.md must exist for developer guidance."""
        assert (ROOT / "CLAUDE.md").exists()

    def test_tasks_md_present(self):
        """The historical TASKS.md tombstone must remain discoverable."""
        assert (ROOT / "TASKS.md").exists()

    def test_requirements_txt_present(self):
        """requirements.txt must exist for dependency installation."""
        assert (ROOT / "requirements.txt").exists()

    def test_pytest_ini_present(self):
        """pytest.ini must exist for test configuration."""
        assert (ROOT / "pytest.ini").exists()


class TestContinuityScript:
    """The continuity check script itself must exist and be runnable."""

    def test_check_continuity_script_present(self):
        """scripts/check_continuity_state.py must exist."""
        assert (ROOT / "scripts" / "check_continuity_state.py").exists()


class TestSoulFileIntegrity:
    """config/SOUL.md must not be empty and must contain key sections."""

    def test_soul_not_empty(self):
        """SOUL.md must contain substantive content (more than 100 chars)."""
        soul = (ROOT / "config" / "SOUL.md").read_text(encoding="utf-8")
        assert len(soul.strip()) > 100, "SOUL.md appears empty or too short"

    def test_soul_has_identity_content(self):
        """SOUL.md must reference Kitty by name."""
        soul = (ROOT / "config" / "SOUL.md").read_text(encoding="utf-8").lower()
        assert "kitty" in soul, "SOUL.md doesn't mention Kitty by name"


class TestEnvExampleCompleteness:
    """Every key in .env.example must have a documented entry."""

    def test_anthropic_key_documented(self):
        """.env.example must document ANTHROPIC_API_KEY."""
        text = (ROOT / ".env.example").read_text(encoding="utf-8")
        assert "ANTHROPIC_API_KEY" in text

    def test_no_hardcoded_secrets(self):
        """.env.example must not contain real API key values."""
        text = (ROOT / ".env.example").read_text(encoding="utf-8")
        # Env example should never contain real keys (they follow sk-ant- or similar patterns)
        assert "sk-ant-api03" not in text
        assert "sk-proj-" not in text


class TestGatewayStructure:
    """Key gateway modules must be present."""

    REQUIRED_MODULES = [
        "app.py",
        "llm_client.py",
        "context_assembler.py",
        "memory_graph.py",
        "buddy.py",
        "paths.py",
        "skill_registry.py",
    ]

    def test_required_gateway_modules_exist(self):
        """All required gateway modules must be present."""
        missing = [
            m for m in self.REQUIRED_MODULES
            if not (ROOT / "gateway" / m).exists()
        ]
        assert not missing, f"Missing gateway modules: {missing}"
