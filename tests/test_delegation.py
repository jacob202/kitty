"""Tests for the delegation packet generator (docs/packets/007)."""

from pathlib import Path

import pytest

from gateway import action_queue, delegation


@pytest.fixture(autouse=True)
def fixed_today(monkeypatch):
    monkeypatch.setattr(delegation, "_today", lambda: "2026-07-04")


@pytest.fixture
def full_action():
    return {
        "id": 42,
        "packet_number": 15,
        "payload": {
            "title": "Fix the frobnicator",
            "executor_type": "Claude Code",
            "purpose": "Make frobnication reliable.",
            "scope": ["Update frob()", "Add tests"],
            "files_touched": "- gateway/frob.py\n- tests/test_frob.py",
            "files_not_to_touch": "- gateway/ui.py",
            "steps": "1. Reproduce\n2. Fix\n3. Test",
            "acceptance": "- Tests pass",
            "verification_commands": "pytest tests/test_frob.py",
            "risks": "- Breaking change",
            "too_broad_if": "It refactors the whole module.",
            "jacob_reviews": "- The API change",
        },
    }


@pytest.fixture
def sparse_action():
    return {"id": 7, "packet_number": 2, "payload": {"title": "Sparse task"}}


def _golden(name: str) -> str:
    return Path(__file__).with_suffix("").parent / "golden" / name


def test_render_full_matches_golden(full_action):
    expected = _golden("packet_delegate_full.md").read_text(encoding="utf-8")
    assert delegation.render_packet(full_action) == expected


def test_render_sparse_shows_unfilled_markers(sparse_action):
    expected = _golden("packet_delegate_sparse.md").read_text(encoding="utf-8")
    assert delegation.render_packet(sparse_action) == expected


def test_next_packet_number_is_max_plus_one(tmp_path, monkeypatch):
    monkeypatch.setattr(delegation, "PACKET_DIR", tmp_path)
    (tmp_path / "001-foo.md").write_text("x", encoding="utf-8")
    (tmp_path / "003-bar.md").write_text("x", encoding="utf-8")
    assert delegation.next_packet_number() == 4


def test_write_packet_refuses_overwrite(tmp_path, monkeypatch, full_action):
    monkeypatch.setattr(delegation, "PACKET_DIR", tmp_path)
    monkeypatch.setattr(delegation, "PACKETS_README", tmp_path / "README.md")
    (tmp_path / "015-fix-the-frobnicator.md").write_text("x", encoding="utf-8")
    (tmp_path / "README.md").write_text(
        "# P\n\n| # | Packet | Best executor | Status |\n|---|---|---|---|\n", encoding="utf-8"
    )

    with pytest.raises(FileExistsError):
        delegation.write_packet(full_action)

    assert (tmp_path / "015-fix-the-frobnicator.md").read_text(encoding="utf-8") == "x"


def test_write_packet_creates_file_and_updates_registry(tmp_path, monkeypatch, full_action):
    monkeypatch.setattr(delegation, "PACKET_DIR", tmp_path)
    monkeypatch.setattr(delegation, "PACKETS_README", tmp_path / "README.md")
    (tmp_path / "README.md").write_text(
        "# P\n\n| # | Packet | Best executor | Status |\n|---|---|---|---|\n", encoding="utf-8"
    )

    path = delegation.write_packet(full_action)

    assert path == tmp_path / "015-fix-the-frobnicator.md"
    assert path.exists()
    assert "Fix the frobnicator" in path.read_text(encoding="utf-8")

    readme = (tmp_path / "README.md").read_text(encoding="utf-8")
    assert "Fix the frobnicator" in readme
    assert "✏️ draft (generated)" in readme


def test_write_packet_twice_appends_two_registry_rows(tmp_path, monkeypatch, full_action):
    monkeypatch.setattr(delegation, "PACKET_DIR", tmp_path)
    monkeypatch.setattr(delegation, "PACKETS_README", tmp_path / "README.md")
    (tmp_path / "README.md").write_text(
        "# P\n\n| # | Packet | Best executor | Status |\n|---|---|---|---|\n", encoding="utf-8"
    )

    delegation.write_packet(full_action)
    delegation.write_packet(
        {
            **full_action,
            "packet_number": 16,
            "payload": {**full_action["payload"], "title": "Second packet"},
        }
    )

    readme = (tmp_path / "README.md").read_text(encoding="utf-8")
    assert readme.count("✏️ draft (generated)") == 2
    assert readme.count("Fix the frobnicator") == 1
    assert readme.count("Second packet") == 1


def test_write_packet_bad_readme_fails_loud(tmp_path, monkeypatch, full_action):
    monkeypatch.setattr(delegation, "PACKET_DIR", tmp_path)
    monkeypatch.setattr(delegation, "PACKETS_README", tmp_path / "README.md")
    (tmp_path / "README.md").write_text("not a table\n", encoding="utf-8")

    with pytest.raises(ValueError, match="could not parse registry table"):
        delegation.write_packet(full_action)


# --- Action-queue integration ------------------------------------------------


@pytest.fixture(autouse=True)
def isolate(monkeypatch, tmp_path):
    """Isolated DB, drafts dir, and packet store; registry from the real tier file."""
    db_file = tmp_path / "kitty" / "kitty.db"
    monkeypatch.setattr(action_queue, "ACTIONS_DB_FILE", db_file, raising=False)
    monkeypatch.setattr(action_queue, "DRAFTS_DIR", tmp_path / "drafts", raising=False)
    monkeypatch.setattr(delegation, "PACKET_DIR", tmp_path / "packets", raising=False)
    monkeypatch.setattr(
        delegation, "PACKETS_README", tmp_path / "packets" / "README.md", raising=False
    )
    (tmp_path / "packets").mkdir(parents=True, exist_ok=True)
    (tmp_path / "packets" / "README.md").write_text(
        "# P\n\n| # | Packet | Best executor | Status |\n|---|---|---|---|\n", encoding="utf-8"
    )
    action_queue.reload_registry()
    yield
    monkeypatch.undo()
    action_queue.reload_registry()


def test_packet_delegate_is_t1():
    action = action_queue.propose(
        source_kind="manual",
        kind="packet.delegate",
        title="Test packet",
        preview="will generate packet",
        payload={"title": "Test packet"},
    )
    assert action["risk_tier"] == "T1"


def test_t1_packet_delegate_writes_local_file_from_proposed():
    action = action_queue.propose(
        source_kind="manual",
        kind="packet.delegate",
        title="Auto packet",
        preview="will generate packet",
        payload={"title": "Auto packet"},
    )
    assert action["status"] == "proposed"

    done = action_queue.execute(action["id"])

    assert done["status"] == "executed"
    assert "packet written to" in done["result"]
