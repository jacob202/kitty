from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ADR = ROOT / "docs" / "adr" / "0039-kitty-native-product-surface.md"
PLAN = ROOT / "docs" / "campaigns" / "product-surface-convergence-PLAN.md"


def test_kitty_native_ui_is_the_canonical_product_surface() -> None:
    text = ADR.read_text(encoding="utf-8").lower()
    assert "kitty's native frontend is the canonical user-facing product surface" in text
    assert "open webui" in text
    assert "not the product shell" in text


def test_model_picker_stays_curated_but_informed() -> None:
    text = ADR.read_text(encoding="utf-8").lower()
    assert "model choice remains first-class" in text
    assert "curated rather than exhaustive" in text
    assert "approximate cost" in text
    assert "manual control" in text
    assert "quality or latency require evidence" in text


def test_image_lab_remains_a_dedicated_conversational_workspace() -> None:
    text = ADR.read_text(encoding="utf-8").lower()
    assert "first-class dedicated workspace" in text
    assert "interaction inside the workspace is conversational" in text
    assert "1/2/4-image batches" in text
    assert "persistent working objects" in text
    assert "duration estimates" in text


def test_plan_records_the_recovery_boundary() -> None:
    text = PLAN.read_text(encoding="utf-8")
    assert "37d3a4eb1f7bdcb7cc84b19dadea519003933cd6" in text
    assert "every restored phase must be reimplemented and reverified" in text
