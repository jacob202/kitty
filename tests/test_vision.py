from unittest.mock import patch

from gateway.vision import describe_schematic


def test_describe_schematic_uses_kitty_smart_route():
    with patch("gateway.vision.call_llm", return_value="description") as mock_call:
        result = describe_schematic(b"\x89PNG\r\n\x1a\n", media_type="image/png")

    assert result == "description"
    mock_call.assert_called_once()
    _, kwargs = mock_call.call_args
    assert kwargs["model"] == "kitty-smart"
    assert kwargs["messages"][0]["content"][1]["image_url"]["url"].startswith("data:image/png;base64,")
