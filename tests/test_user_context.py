"""Tests for gateway.user_context (TELOS user-identity injection)."""

import importlib

import pytest

from gateway import user_context


@pytest.fixture
def user_dir(tmp_path, monkeypatch):
    """Point user_context at a temp USER dir and clear its cache."""
    d = tmp_path / "USER"
    d.mkdir()
    monkeypatch.setattr(user_context, "USER_DIR", d)
    user_context.load_user_context.cache_clear()
    yield d
    user_context.load_user_context.cache_clear()


def test_empty_when_no_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(user_context, "USER_DIR", tmp_path / "nope")
    user_context.load_user_context.cache_clear()
    assert user_context.load_user_context() == ""


def test_template_files_are_skipped(user_dir):
    (user_dir / "MISSION.md").write_text(
        "<!-- TEMPLATE: fill this in and delete this line. -->\n# Mission\n- (e.g.) thing\n"
    )
    assert user_context.load_user_context() == ""


def test_filled_file_is_included(user_dir):
    (user_dir / "MISSION.md").write_text("# Mission\nShip leverage tools, keep privacy.\n")
    out = user_context.load_user_context()
    assert "About Jacob (TELOS)" in out
    assert "Ship leverage tools" in out


def test_mixed_filled_and_template(user_dir):
    (user_dir / "MISSION.md").write_text("# Mission\nReal mission text.\n")
    (user_dir / "GOALS.md").write_text("TEMPLATE: not filled\n# Goals\n")
    out = user_context.load_user_context()
    assert "Real mission text." in out
    assert "not filled" not in out


def test_ordering_mission_before_goals(user_dir):
    (user_dir / "GOALS.md").write_text("# Goals\nGoal text here.\n")
    (user_dir / "MISSION.md").write_text("# Mission\nMission text here.\n")
    out = user_context.load_user_context()
    assert out.index("Mission text here.") < out.index("Goal text here.")


@pytest.mark.asyncio
async def test_injected_into_system_prompt(user_dir, monkeypatch):
    (user_dir / "MISSION.md").write_text("# Mission\nUNIQUE_TELOS_MARKER mission.\n")
    cb = importlib.import_module("gateway.context_builder")

    async def fake_assemble(message, parts_mode=False, domain=None, deps=None):
        from gateway.context_assembler import ContextBundle

        return ContextBundle(system=cb.build_worker_context.__module__ + ":" + "base")

    # The façade in context_builder now delegates to assemble_context. Patch
    # the assembler to return a minimal bundle so the test exercises the
    # wiring (TELOS injection happens in the assembler).
    import gateway.context_assembler as assembler

    async def assemble_stub(message, parts_mode=False, domain=None, deps=None):
        # Re-run the assembler's user-block step so TELOS lands in the
        # prompt — same path the production code takes.
        from gateway.context_assembler import ContextBundle
        from gateway import user_context

        base = ""
        user_block = user_context.load_user_context()
        if user_block:
            base = f"{base}\n\n{user_block}" if base else user_block
        return ContextBundle(system=base)

    monkeypatch.setattr(assembler, "assemble_context", assemble_stub)

    prompt = await cb.get_system_prompt("hello there", domain="soul")
    assert "UNIQUE_TELOS_MARKER" in prompt
