"""
Skill runtime discovery contract tests.

Verifies that .agents/skills/ has valid skill definitions that can be discovered
at runtime. These run with only pytest installed — no gateway imports.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS_ROOT = ROOT / ".agents" / "skills"

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)
_KEY_RE = re.compile(r"^(\w[\w_-]*):\s*(.*)$")


def _parse_frontmatter(text: str) -> dict:
    """Extract key/value pairs from YAML frontmatter delimited by --- lines."""
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}
    result = {}
    for line in m.group(1).splitlines():
        km = _KEY_RE.match(line.strip())
        if km:
            result[km.group(1)] = km.group(2).strip()
    return result


def _all_skill_files() -> list[Path]:
    """Return all SKILL.md paths under the skills root, or an empty list."""
    if not SKILLS_ROOT.exists():
        return []
    return list(SKILLS_ROOT.rglob("SKILL.md"))


class TestSkillDirectoryExists:
    """Verify the .agents/skills/ directory exists and is populated."""

    def test_skills_root_exists(self):
        """The skills root directory must be present."""
        assert SKILLS_ROOT.exists(), f".agents/skills/ not found at {SKILLS_ROOT}"

    def test_at_least_one_skill(self):
        """At least one SKILL.md must exist under the skills root."""
        files = _all_skill_files()
        assert files, f"No SKILL.md files found under {SKILLS_ROOT}"


class TestSkillFileStructure:
    """Verify every SKILL.md has valid YAML frontmatter with required fields."""

    def test_each_skill_has_frontmatter(self):
        """Every SKILL.md must open with a --- delimited YAML block."""
        bad = []
        for path in _all_skill_files():
            text = path.read_text(encoding="utf-8")
            if not _FRONTMATTER_RE.match(text):
                bad.append(str(path))
        assert not bad, f"Skills missing YAML frontmatter: {bad}"

    def test_each_skill_has_name(self):
        """Every SKILL.md frontmatter must contain a non-empty 'name' field."""
        bad = []
        for path in _all_skill_files():
            text = path.read_text(encoding="utf-8")
            meta = _parse_frontmatter(text)
            if not meta.get("name"):
                bad.append(str(path))
        assert not bad, f"Skills missing 'name' field: {bad}"

    def test_each_skill_has_description(self):
        """Every SKILL.md frontmatter must contain a non-empty 'description' field."""
        bad = []
        for path in _all_skill_files():
            text = path.read_text(encoding="utf-8")
            meta = _parse_frontmatter(text)
            if not meta.get("description"):
                bad.append(str(path))
        assert not bad, f"Skills missing 'description' field: {bad}"

    def test_skill_names_are_slug_format(self):
        """Skill names should be lowercase-hyphenated for consistent routing."""
        bad = []
        for path in _all_skill_files():
            text = path.read_text(encoding="utf-8")
            meta = _parse_frontmatter(text)
            name = meta.get("name", "")
            if name and not re.match(r"^[a-z0-9][a-z0-9-]*$", name):
                bad.append(f"{path}: name={name!r}")
        assert not bad, f"Skill names not in slug format: {bad}"

    def test_skill_names_unique(self):
        """No two skills may share the same name field."""
        names = []
        for path in _all_skill_files():
            text = path.read_text(encoding="utf-8")
            meta = _parse_frontmatter(text)
            if meta.get("name"):
                names.append(meta["name"])
        duplicates = [n for n in names if names.count(n) > 1]
        assert not duplicates, f"Duplicate skill names: {set(duplicates)}"


class TestKnownSkills:
    """Spot-check that expected skills are present and valid."""

    EXPECTED = ["journal-entry"]

    def test_expected_skills_present(self):
        """Each skill in EXPECTED must be discoverable by name."""
        found_names = set()
        for path in _all_skill_files():
            text = path.read_text(encoding="utf-8")
            meta = _parse_frontmatter(text)
            if meta.get("name"):
                found_names.add(meta["name"])

        missing = [s for s in self.EXPECTED if s not in found_names]
        assert not missing, f"Expected skills not found: {missing}"
