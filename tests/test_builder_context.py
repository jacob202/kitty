"""Tests for privacy-bounded, collision-safe Builder context manifests."""

from pathlib import Path

from gateway.builder_context import build_context_manifest, write_run_manifest


def test_context_manifest_hashes_instructions_and_skills_without_contents(tmp_path: Path):
    (tmp_path / "AGENTS.md").write_text("rules\n")
    (tmp_path / "opencode.jsonc").write_text("{}\n")
    skill = tmp_path / ".agents" / "skills" / "demo"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("---\nname: demo\n---\n")
    (tmp_path / ".env").write_text("SECRET=do-not-record\n")
    bundle = tmp_path / "bundle.json"
    bundle.write_text('{"objective":"test"}\n')

    manifest = build_context_manifest(tmp_path, bundle)

    paths = {entry["path"] for entry in manifest["context_files"]}
    assert "AGENTS.md" in paths
    assert ".agents/skills/demo/SKILL.md" in paths
    assert ".env" not in paths
    assert manifest["task_bundle"]["sha256"]
    assert all("do-not-record" not in str(entry) for entry in manifest.values())


def test_run_manifest_write_is_atomic_and_versioned(tmp_path: Path):
    path = tmp_path / "attempt" / "run-manifest.json"
    write_run_manifest(path, {"task_id": "task-1", "outcome": "running"})

    assert path.exists()
    payload = path.read_text()
    assert '"manifest_version": 1' in payload
    assert '"task_id": "task-1"' in payload
    assert not list(path.parent.glob("*.tmp"))
