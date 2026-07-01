from gateway import state_composer


def test_compose_now_returns_response_envelope():
    result = state_composer.compose_now(timeout_seconds=0.5)
    assert set(result) == {"generated_at", "schema_version", "sections", "errors"}
    assert result["schema_version"] == 1
