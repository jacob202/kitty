"""Weather — current conditions for Regina via wttr.in.

Cached 30 minutes. Silent fallback when offline.

Public API:
  get_weather() -> dict
  get_weather_text() -> str   One-line summary for context injection
"""
from __future__ import annotations

import logging
import time
from typing import Optional

import requests

logger = logging.getLogger("kitty.weather")

WTTR_URL = "https://wttr.in/Regina?format=j1"
CACHE_TTL = 1800  # 30 minutes

_cache: Optional[dict] = None
_cache_ts: float = 0.0


def get_weather() -> dict:
    """Fetch current weather for Regina. Returns cached data if fresh."""
    global _cache, _cache_ts

    now = time.time()
    if _cache and (now - _cache_ts) < CACHE_TTL:
        return _cache

    try:
        resp = requests.get(WTTR_URL, timeout=5, headers={"User-Agent": "KittyWeather/1.0"})
        resp.raise_for_status()
        data = resp.json()
        _cache = _parse(data)
        _cache_ts = now
        return _cache
    except Exception as e:
        logger.warning("Weather fetch failed: %s", e)
        return {}


def _parse(raw: dict) -> dict:
    """Extract the fields we actually care about from wttr.in JSON."""
    try:
        current = raw["current_condition"][0]
        today = raw["weather"][0]
        return {
            "temp_c":       int(current.get("temp_C", 0)),
            "feels_like_c": int(current.get("FeelsLikeC", 0)),
            "description":  current.get("weatherDesc", [{}])[0].get("value", ""),
            "humidity":     int(current.get("humidity", 0)),
            "wind_kmph":    int(current.get("windspeedKmph", 0)),
            "max_c":        int(today.get("maxtempC", 0)),
            "min_c":        int(today.get("mintempC", 0)),
        }
    except Exception:
        return {}


def get_weather_text() -> str:
    """Return a one-line weather summary for context/brief injection."""
    w = get_weather()
    if not w:
        return ""
    desc = w.get("description", "")
    temp = w.get("temp_c", "?")
    feels = w.get("feels_like_c", "?")
    hi = w.get("max_c", "?")
    lo = w.get("min_c", "?")
    return f"Regina weather: {desc}, {temp}°C (feels {feels}°C), high {hi}°C / low {lo}°C"
