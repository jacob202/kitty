from pathlib import Path

import pytest

from scripts.openviking_kb_build import (
    ALLOWED_DIRS,
    ALLOWED_ROOT_FILES,
    build_plan,
    command_for,
    git_head,
    target_for_generation,
)


def test_target_for_generation_is_immutable_sibling() -> None:
    assert target_for_generation("20260901-a") == "viking://resources/kitty-kb-20260901-a"
    assert target_for_generation("run/2") == "viking://resources/kitty-kb-run-2"
    with pytest.raises(ValueError):
        target_for_generation("   ")


def test_build_plan_excludes_private_and_evidence_paths(tmp_path: Path) -> None:
    for name in ALLOWED_DIRS:
        (tmp_path / name).mkdir()
    for name in ALLOWED_ROOT_FILES:
        (tmp_path / name).write_text("ok")
    for name in ("identity.md", "PREFERENCES.md", "raw", "metrics", "workflow-signals"):
        path = tmp_path / name
        path.mkdir() if "." not in name else path.write_text("private")
    (tmp_path / "review-123.json").write_text("{}")

    plan = build_plan(tmp_path, "viking://resources/kitty-kb-g1")
    sources = {source.relative_to(tmp_path).as_posix() for source, _ in plan}
    assert sources == set(ALLOWED_DIRS) | set(ALLOWED_ROOT_FILES)


def test_command_is_vectors_only_create_only(tmp_path: Path) -> None:
    source = tmp_path / "wiki"
    source.mkdir()
    cmd = command_for(source, "viking://resources/kitty-kb-g1/wiki", "/usr/bin/ov")
    assert cmd[:3] == ["/usr/bin/ov", "add-resource", str(source)]
    assert cmd[3:5] == ["--to", "viking://resources/kitty-kb-g1/wiki"]
    assert ["--processing-mode", "vectors_only"] == cmd[5:7]
    assert "--wait" in cmd
    assert "rm" not in cmd


def test_git_head_returns_none_outside_repo(tmp_path: Path) -> None:
    assert git_head(tmp_path) is None
