"""Tests for DTH-05: Skill bundle import with DeepTutor-grade safety."""

from __future__ import annotations

import zipfile
from io import BytesIO
from pathlib import Path

import pytest

from gateway.skill_import import (
    SkillImportError,
    _reject_binary_payload,
    _skill_name_from,
    import_skill_bundle,
)

VALID_SKILL_MD = b"""---
name: test-skill
description: A test skill for unit tests
---
# Test Skill

This is a test skill.
"""


def _make_zip(files: dict[str, bytes], path: Path | None = None) -> Path:
    """Create a zip file with the given name->content mapping."""
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in files.items():
            zf.writestr(name, data)
    if path is None:
        path = Path("/tmp/test-skill.zip")
    path.write_bytes(buf.getvalue())
    return path


# ── _reject_binary_payload ───────────────────────────────────────────────────


class TestRejectBinaryPayload:
    def test_rejects_exe(self):
        with pytest.raises(SkillImportError, match="binary payload"):
            _reject_binary_payload("evil.exe", b"MZ" + b"\x00" * 100)

    def test_rejects_zip(self):
        with pytest.raises(SkillImportError, match="binary payload"):
            _reject_binary_payload("archive.zip", b"PK\x03\x04" + b"\x00" * 100)

    def test_rejects_gzip(self):
        with pytest.raises(SkillImportError, match="binary payload"):
            _reject_binary_payload("data.gz", b"\x1f\x8b" + b"\x00" * 100)

    def test_rejects_elf(self):
        with pytest.raises(SkillImportError, match="binary payload"):
            _reject_binary_payload("binary", b"\x7fELF" + b"\x00" * 100)

    def test_rejects_ole(self):
        with pytest.raises(SkillImportError, match="binary payload"):
            _reject_binary_payload("old.doc", b"OLE\x00" + b"\x00" * 100)

    def test_accepts_text(self):
        _reject_binary_payload("readme.md", b"# Hello\nThis is text.")

    def test_accepts_json(self):
        _reject_binary_payload("data.json", b'{"key": "value"}')

    def test_rejects_binary_in_allowed_extension(self):
        """Binary payload rejected even if extension is .md."""
        with pytest.raises(SkillImportError, match="binary payload"):
            _reject_binary_payload("disguised.md", b"MZ" + b"\x00" * 100)


# ── _skill_name_from ─────────────────────────────────────────────────────────


class TestSkillNameFrom:
    def test_valid(self):
        assert _skill_name_from(VALID_SKILL_MD.decode()) == "test-skill"

    def test_no_frontmatter(self):
        with pytest.raises(SkillImportError, match="no YAML frontmatter"):
            _skill_name_from("# Just a heading\nNo frontmatter.")

    def test_unterminated_frontmatter(self):
        with pytest.raises(SkillImportError, match="unterminated"):
            _skill_name_from("---\nname: x\n# No closing")

    def test_missing_name(self):
        with pytest.raises(SkillImportError, match="missing 'name'"):
            _skill_name_from("---\ndescription: no name field\n---")

    def test_invalid_name_chars(self):
        with pytest.raises(SkillImportError, match="invalid skill name"):
            _skill_name_from("---\nname: spaces not allowed\n---")

    def test_name_with_hyphens_ok(self):
        assert _skill_name_from("---\nname: my-cool-skill\n---") == "my-cool-skill"

    def test_name_with_underscores_ok(self):
        assert _skill_name_from("---\nname: my_skill\n---") == "my_skill"


# ── import_skill_bundle ──────────────────────────────────────────────────────


class TestImportSkillBundle:
    def test_valid_bundle(self, tmp_path: Path):
        zip_path = _make_zip(
            {"SKILL.md": VALID_SKILL_MD, "data.txt": b"some data"},
            tmp_path / "bundle.zip",
        )
        dest = tmp_path / "skills"
        result = import_skill_bundle(zip_path, target_root=dest)
        assert result.name == "test-skill"
        assert result.path.is_dir()
        assert "SKILL.md" in result.files
        assert "data.txt" in result.files

    def test_not_a_zip(self, tmp_path: Path):
        fake = tmp_path / "not-a.zip"
        fake.write_bytes(b"not a zip")
        with pytest.raises(SkillImportError, match="corrupt or tampered"):
            import_skill_bundle(fake, target_root=tmp_path / "skills")

    def test_missing_skill_md(self, tmp_path: Path):
        zip_path = _make_zip(
            {"readme.txt": b"no skill md here"},
            tmp_path / "no-skill-md.zip",
        )
        with pytest.raises(SkillImportError, match="no SKILL.md"):
            import_skill_bundle(zip_path, target_root=tmp_path / "skills")

    def test_rejects_executable(self, tmp_path: Path):
        zip_path = _make_zip(
            {"SKILL.md": VALID_SKILL_MD, "evil.exe": b"MZ" + b"\x00" * 50},
            tmp_path / "evil.zip",
        )
        with pytest.raises(SkillImportError, match="rejected file type"):
            import_skill_bundle(zip_path, target_root=tmp_path / "skills")

    def test_rejects_bad_extension(self, tmp_path: Path):
        zip_path = _make_zip(
            {"SKILL.md": VALID_SKILL_MD, "script.py": b"print('hello')"},
            tmp_path / "bad-ext.zip",
        )
        with pytest.raises(SkillImportError, match="rejected file type"):
            import_skill_bundle(zip_path, target_root=tmp_path / "skills")

    def test_too_many_entries(self, tmp_path: Path):
        files = {f"file{i}.txt": b"x" for i in range(300)}
        files["SKILL.md"] = VALID_SKILL_MD
        zip_path = _make_zip(files, tmp_path / "many.zip")
        with pytest.raises(SkillImportError, match="too many entries"):
            import_skill_bundle(zip_path, target_root=tmp_path / "skills")

    def test_corrupt_zip(self, tmp_path: Path):
        corrupt = tmp_path / "corrupt.zip"
        corrupt.write_bytes(b"PK\x03\x04" + b"\x00" * 100)
        with pytest.raises(SkillImportError, match="corrupt or tampered"):
            import_skill_bundle(corrupt, target_root=tmp_path / "skills")

    def test_already_exists(self, tmp_path: Path):
        zip_path = _make_zip(
            {"SKILL.md": VALID_SKILL_MD},
            tmp_path / "existing.zip",
        )
        dest = tmp_path / "skills"
        dest.mkdir()
        (dest / "test-skill").mkdir()
        with pytest.raises(SkillImportError, match="already exists"):
            import_skill_bundle(zip_path, target_root=dest)

    def test_file_not_found(self, tmp_path: Path):
        with pytest.raises(SkillImportError, match="bundle not found"):
            import_skill_bundle(
                tmp_path / "nonexistent.zip", target_root=tmp_path / "skills"
            )
