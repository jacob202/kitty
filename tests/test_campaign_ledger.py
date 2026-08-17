"""Campaign ledger — the ledger must not be able to lie.

The whole point of scripts/campaign.py is that `verified` is unforgeable:
it requires a passing command AND a real commit. These tests pin exactly
that, plus round-trip parsing and the resume liar-detection path.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import campaign  # noqa: E402


@pytest.fixture()
def repo(tmp_path, monkeypatch):
    """A throwaway git repo with campaign.py operating inside it."""
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    for key, val in (("user.email", "t@example.com"), ("user.name", "T")):
        subprocess.run(["git", "-C", str(tmp_path), "config", key, val], check=True)
    (tmp_path / "seed.txt").write_text("seed\n")
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-q", "-m", "seed"], check=True)
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _init(goal="ship it", phases=("one::true",)):
    args = ["--slug", "demo", "init", "--goal", goal]
    for spec in phases:
        args += ["--phase", spec]
    return campaign.main(args)


def test_init_creates_committed_ledger(repo):
    assert _init() == 0
    path = repo / "docs/campaigns/demo.md"
    assert path.exists()
    assert campaign.is_dirty() is False, "init must commit the ledger, not leave WIP"


def test_round_trip_preserves_phases(repo):
    _init(phases=("one::true", "two::false"))
    camp = campaign.parse(repo / "docs/campaigns/demo.md")
    assert [p.name for p in camp.phases] == ["one", "two"]
    assert [p.verify for p in camp.phases] == ["true", "false"]
    assert camp.goal == "ship it"
    assert all(p.status == "pending" for p in camp.phases)


def test_verify_marks_verified_and_records_commit(repo):
    _init(phases=("one::true",))
    assert campaign.main(["--slug", "demo", "verify", "1"]) == 0
    camp = campaign.parse(repo / "docs/campaigns/demo.md")
    assert camp.phases[0].status == "verified"
    assert campaign.commit_exists(camp.phases[0].commit)


def test_failing_command_cannot_reach_verified(repo):
    _init(phases=("one::false",))
    assert campaign.main(["--slug", "demo", "verify", "1"]) == 1
    camp = campaign.parse(repo / "docs/campaigns/demo.md")
    assert camp.phases[0].status == "in-progress"
    assert camp.phases[0].commit == ""


def test_dirty_tree_cannot_reach_verified(repo):
    _init(phases=("one::true",))
    (repo / "wip.txt").write_text("uncommitted\n")
    assert campaign.main(["--slug", "demo", "verify", "1"]) == 1
    camp = campaign.parse(repo / "docs/campaigns/demo.md")
    assert camp.phases[0].status == "pending"


def test_audit_flags_hand_edited_verified(repo):
    _init(phases=("one::true",))
    path = repo / "docs/campaigns/demo.md"
    path.write_text(path.read_text().replace("| pending |", "| verified |"))
    assert campaign.main(["--slug", "demo", "audit"]) == 1


def test_audit_clean_after_real_verify(repo):
    _init(phases=("one::true",))
    campaign.main(["--slug", "demo", "verify", "1"])
    assert campaign.main(["--slug", "demo", "audit"]) == 0


def test_resume_detects_a_lying_ledger(repo, capsys):
    """Verified once, then break the command: resume must call it out."""
    _init(phases=("one::test -f proof.txt",))
    (repo / "proof.txt").write_text("x\n")
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "proof"], check=True)
    assert campaign.main(["--slug", "demo", "verify", "1"]) == 0

    (repo / "proof.txt").unlink()
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "drop"], check=True)
    assert campaign.main(["--slug", "demo", "resume"]) == 1
    assert "LEDGER LIES" in capsys.readouterr().out


def test_resume_clean_when_ledger_is_honest(repo):
    _init(phases=("one::true", "two::true"))
    campaign.main(["--slug", "demo", "verify", "1"])
    assert campaign.main(["--slug", "demo", "resume"]) == 0


def test_resume_flags_uncommitted_wip(repo):
    _init(phases=("one::true",))
    (repo / "wip.txt").write_text("half-done\n")
    assert campaign.main(["--slug", "demo", "resume"]) == 1


def test_summary_is_ten_lines(repo):
    _init(phases=("one::true",))
    camp = campaign.parse(repo / "docs/campaigns/demo.md")
    assert len(campaign.summary(camp).splitlines()) == 10


def test_handoff_records_single_next_action(repo):
    _init(phases=("one::true", "two::true"))
    campaign.main(["--slug", "demo", "verify", "1"])
    assert campaign.main(["--slug", "demo", "handoff"]) == 0
    text = (repo / "docs/campaigns/demo.md").read_text()
    assert "**Single next action:**" in text
    assert "two" in text.split("## Handoff", 1)[1]


def test_malformed_status_fails_loud(repo):
    _init(phases=("one::true",))
    path = repo / "docs/campaigns/demo.md"
    path.write_text(path.read_text().replace("| pending |", "| donezo |"))
    with pytest.raises(campaign.CampaignError, match="not one of"):
        campaign.parse(path)


def test_missing_ledger_fails_loud(repo):
    with pytest.raises(campaign.CampaignError, match="no campaign ledger"):
        campaign.parse(repo / "docs/campaigns/nope.md")
