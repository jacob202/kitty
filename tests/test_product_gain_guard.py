from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from scripts.product_gain_guard import GuardError, analyze_repo, main


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    return repo


def _commit(repo: Path, relpath: str, text: str, message: str) -> None:
    path = repo / relpath
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    _git(repo, "add", relpath)
    _git(repo, "commit", "-q", "-m", message)


def test_infrastructure_only_window_requires_product_answer(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _commit(repo, "scripts/tool.py", "print('infra')\n", "chore: add tool")

    result = analyze_repo(repo, since_days=7)

    assert result["status"] == "needs_product_answer"
    assert result["product_ratio"] == 0.0
    assert result["minimum_product_ratio"] == pytest.approx(0.20)
    assert result["needs_product_answer"] is True
    assert len(result["infrastructure_only_commits"]) == 1
    assert result["product_touch_commits"] == []
    assert main(["--repo", str(repo), "--enforce"]) == 2


def test_product_touch_satisfies_default_ratio_without_claiming_runtime_proof(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path)
    _commit(repo, "scripts/tool.py", "print('infra')\n", "chore: add tool")
    _commit(repo, "gateway/routes/chat.py", "VALUE = 1\n", "feat: product")

    result = analyze_repo(repo, since_days=7)

    assert result["status"] == "product_evidence_present"
    assert result["product_ratio"] == pytest.approx(0.5)
    assert result["needs_product_answer"] is False
    assert "does not prove" in result["note"]


def test_ratio_guard_catches_low_product_share_not_only_zero_product(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _commit(repo, "gateway/routes/chat.py", "VALUE = 1\n", "feat: product")
    for index in range(4):
        _commit(
            repo,
            f"scripts/tool_{index}.py",
            f"VALUE = {index}\n",
            f"chore: infra {index}",
        )

    result = analyze_repo(repo, since_days=7, minimum_product_ratio=0.25)

    assert result["product_ratio"] == pytest.approx(0.20)
    assert result["needs_product_answer"] is True
    assert main(
        [
            "--repo",
            str(repo),
            "--min-product-ratio",
            "0.25",
            "--enforce",
        ]
    ) == 2


def test_ratio_floor_must_be_between_zero_and_one(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    with pytest.raises(GuardError, match="between 0 and 1"):
        analyze_repo(repo, minimum_product_ratio=1.1)
