"""Tests for gateway.vision — Claude Sonnet schematic analysis."""
import pytest
from unittest.mock import patch, MagicMock


def test_describe_schematic_calls_anthropic(monkeypatch):
    """describe_schematic() calls Anthropic messages.create with base64 image."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    mock_content = MagicMock()
    mock_content.text = "A 555 timer oscillator circuit with R1=10kΩ, R2=4.7kΩ, C=10µF."
    mock_response = MagicMock()
    mock_response.content = [mock_content]

    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_response

    with patch("gateway.vision.anthropic.Anthropic", return_value=mock_client):
        import importlib
        import gateway.vision as vision_mod
        importlib.reload(vision_mod)
        result = vision_mod.describe_schematic(b"fake-image-bytes", "image/png")

    assert "555 timer" in result
    call_kwargs = mock_client.messages.create.call_args[1]
    assert call_kwargs["model"].startswith("claude-")
    assert call_kwargs["max_tokens"] >= 512


def test_describe_schematic_no_api_key_returns_empty(monkeypatch):
    """describe_schematic() returns '' and logs warning when ANTHROPIC_API_KEY unset."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    import importlib
    import gateway.vision as vision_mod
    importlib.reload(vision_mod)

    result = vision_mod.describe_schematic(b"fake-image-bytes", "image/png")
    assert result == ""


def test_describe_schematic_api_error_returns_empty(monkeypatch):
    """describe_schematic() returns '' when Anthropic raises."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    mock_client = MagicMock()
    mock_client.messages.create.side_effect = Exception("API error")

    with patch("gateway.vision.anthropic.Anthropic", return_value=mock_client):
        import importlib
        import gateway.vision as vision_mod
        importlib.reload(vision_mod)
        result = vision_mod.describe_schematic(b"fake-image-bytes", "image/png")

    assert result == ""
