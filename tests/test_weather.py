"""Tests for weather module — wttr.in fetch with caching."""
import time
from unittest.mock import MagicMock, patch

import gateway.weather as wx


def _mock_resp(data: dict):
    m = MagicMock()
    m.raise_for_status = MagicMock()
    m.json.return_value = data
    return m


SAMPLE_WTTR = {
    "current_condition": [{
        "temp_C": "5",
        "FeelsLikeC": "2",
        "weatherDesc": [{"value": "Overcast"}],
        "humidity": "78",
        "windspeedKmph": "25",
    }],
    "weather": [{
        "maxtempC": "8",
        "mintempC": "-1",
    }],
}


class TestWeatherFetch:
    def setup_method(self):
        wx._cache = None
        wx._cache_ts = 0.0

    def test_returns_parsed_data(self):
        with patch("requests.get", return_value=_mock_resp(SAMPLE_WTTR)):
            data = wx.get_weather()
        assert data["temp_c"] == 5
        assert data["description"] == "Overcast"
        assert data["max_c"] == 8
        assert data["min_c"] == -1

    def test_cache_hit_skips_request(self):
        wx._cache = {"temp_c": 3, "description": "Cached"}
        wx._cache_ts = time.time()
        with patch("requests.get") as mock_get:
            data = wx.get_weather()
            mock_get.assert_not_called()
        assert data["description"] == "Cached"

    def test_network_error_returns_empty(self):
        with patch("requests.get", side_effect=Exception("timeout")):
            data = wx.get_weather()
        assert data == {}

    def test_get_weather_text_format(self):
        with patch("requests.get", return_value=_mock_resp(SAMPLE_WTTR)):
            text = wx.get_weather_text()
        assert "Regina" in text
        assert "5°C" in text
        assert "Overcast" in text

    def test_get_weather_text_empty_on_failure(self):
        wx._cache = None
        wx._cache_ts = 0.0
        with patch("requests.get", side_effect=Exception("offline")):
            text = wx.get_weather_text()
        assert text == ""
