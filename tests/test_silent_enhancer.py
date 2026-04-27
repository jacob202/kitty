from src.core.silent_enhancer import EnhancedPrompt, SilentPromptEnhancer


def test_enhance_structured_returns_typed_spear_components():
    enhancer = SilentPromptEnhancer(use_llm=False)

    result = enhancer.enhance_structured(
        "my Sansui amp has a hum and I am a beginner"
    )

    assert isinstance(result, EnhancedPrompt)
    assert "electronics" in result.role.lower()
    assert "Sansui amp has a hum" in result.problem
    assert "beginner" in result.audience.lower()
    assert "high voltage" in result.restrictions.lower()


def test_enhance_preserves_legacy_string_api():
    enhancer = SilentPromptEnhancer(use_llm=False)

    result = enhancer.enhance("identify this schematic part")

    assert isinstance(result, str)
    assert "System/Role:" in result
    assert "Problem:" in result
    assert "Expectation:" in result
