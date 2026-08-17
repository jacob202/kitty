from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAKEFILE = ROOT / "Makefile"


def test_make_ci_includes_required_hygiene_gates() -> None:
    text = MAKEFILE.read_text(encoding="utf-8")
    first = text.splitlines()[0]
    ci_line = next(line for line in text.splitlines() if line.startswith("ci:"))

    assert "vulture" in first
    assert "lychee" in first
    assert "vulture" in ci_line
    assert "lychee" in ci_line
    assert "vulture gateway/ --min-confidence 80 --exclude gateway/kitty-chat/" in text
    assert "lychee --root-dir docs --no-progress --accept 200,301,302,307,308 docs/" in text
