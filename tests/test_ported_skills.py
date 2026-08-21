"""The PAI-derived reasoning skills are discoverable and clean."""

import pytest

from gateway import skill_registry
from gateway.paths import PROJECT_ROOT

ACTIVE_PORTED = ["isa"]
ARCHIVED_PORTED = [
    "first-principles",
    "systems-thinking",
    "red-team",
    "iterative-depth",
    "root-cause-analysis",
    "extract-wisdom",
    "science-method",
]
PORTED = ACTIVE_PORTED + ARCHIVED_PORTED


@pytest.fixture(scope="module")
def skills():
    return {s["name"]: s for s in skill_registry.discover(force_refresh=True)}


@pytest.mark.parametrize("name", ACTIVE_PORTED)
def test_active_skill_discovered_with_description(skills, name):
    assert name in skills, f"{name} not discovered by skill_registry"
    assert skills[name]["description"].strip(), f"{name} has empty description"


@pytest.mark.parametrize("name", ARCHIVED_PORTED)
def test_archived_skill_not_discovered(skills, name):
    assert name not in skills, f"archived skill {name} surfaced as active"


@pytest.mark.parametrize("name", PORTED)
def test_no_pai_cruft_left(name):
    """No PAI-specific paths, voice hooks, or template vars leaked through the lift."""
    active_dir = PROJECT_ROOT / ".agents" / "skills" / name
    archived_dir = PROJECT_ROOT / ".agents" / "skills" / "_archive" / name
    skill_dir = active_dir if active_dir.exists() else archived_dir
    cruft = ["localhost:31337", "localhost:8888", "~/.claude",
             "PRINCIPAL.NAME", "DAIDENTITY", "SKILLCUSTOMIZATIONS",
             "config/MEMORY/SKILLS"]
    for md in skill_dir.rglob("*.md"):
        text = md.read_text(encoding="utf-8")
        for token in cruft:
            assert token not in text, f"{md} still contains '{token}'"
