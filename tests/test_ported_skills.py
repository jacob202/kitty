"""The PAI-derived reasoning skills are discoverable and clean."""
from pathlib import Path

import pytest

from gateway import skill_registry
from gateway.paths import PROJECT_ROOT

PORTED = [
    "first-principles",
    "systems-thinking",
    "red-team",
    "iterative-depth",
    "root-cause-analysis",
    "extract-wisdom",
    "science-method",
    "isa",
]


@pytest.fixture(scope="module")
def skills():
    return {s["name"]: s for s in skill_registry.discover(force_refresh=True)}


@pytest.mark.parametrize("name", PORTED)
def test_skill_discovered_with_description(skills, name):
    assert name in skills, f"{name} not discovered by skill_registry"
    assert skills[name]["description"].strip(), f"{name} has empty description"


@pytest.mark.parametrize("name", PORTED)
def test_no_pai_cruft_left(name):
    """No PAI-specific paths, voice hooks, or template vars leaked through the lift."""
    skill_dir = PROJECT_ROOT / ".agents" / "skills" / name
    cruft = ["localhost:31337", "localhost:8888", "~/.claude",
             "PRINCIPAL.NAME", "DAIDENTITY", "SKILLCUSTOMIZATIONS",
             "config/MEMORY/SKILLS"]
    for md in skill_dir.rglob("*.md"):
        text = md.read_text(encoding="utf-8")
        for token in cruft:
            assert token not in text, f"{md} still contains '{token}'"
