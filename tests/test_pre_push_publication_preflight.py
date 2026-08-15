"""Regression guard for the publication-environment preflight mode."""

from pathlib import Path


HOOK = Path(__file__).parent.parent / "scripts/hooks/pre-push"


def test_pre_push_hook_exposes_fast_publication_preflight_mode() -> None:
    text = HOOK.read_text(encoding="utf-8")

    assert '"--preflight"' in text
    assert "PREFLIGHT_ONLY" in text
    assert "exit 75" in text
    assert text.index('"--preflight"') < text.index('run_gate "code style"')
