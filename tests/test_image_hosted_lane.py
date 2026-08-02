"""The hosted image lane — the only one that spends money."""

from __future__ import annotations

import importlib

import pytest

from gateway import image_runner


@pytest.fixture
def hosted(monkeypatch):
    monkeypatch.setenv("KITTY_IMAGE_PAID_ENABLED", "1")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    return importlib.reload(image_runner)


@pytest.fixture
def paid_off(monkeypatch):
    monkeypatch.delenv("KITTY_IMAGE_PAID_ENABLED", raising=False)
    return importlib.reload(image_runner)


def test_paid_generation_is_off_until_it_is_switched_on(paid_off):
    """Jacob retired the last paid image provider over cost. Nothing here spends
    until he says so, and the reason has to carry the price and the switch."""
    available, reason = paid_off.openrouter_images_available()

    assert available is False
    assert "7 cents" in reason
    assert "KITTY_IMAGE_PAID_ENABLED" in reason


def test_the_switch_alone_is_not_enough_without_a_key(hosted, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "")
    reloaded = importlib.reload(image_runner)
    monkeypatch.setenv("KITTY_IMAGE_PAID_ENABLED", "1")

    available, reason = reloaded.openrouter_images_available()

    assert available is False
    assert "OPENROUTER_API_KEY" in reason or "off" in reason


def test_the_switch_turns_it_on(hosted):
    available, reason = hosted.openrouter_images_available()

    assert available is True
    assert reason == ""


def test_a_disabled_lane_refuses_before_it_can_charge(paid_off):
    """The refusal must land before the HTTP call, not after."""
    import asyncio

    with pytest.raises(paid_off.ImageRunnerError) as excinfo:
        asyncio.run(paid_off.run("openrouter", "a pear"))

    assert "off" in str(excinfo.value)


def test_openrouter_is_a_dispatchable_engine():
    assert "openrouter" in image_runner.ENGINES
    assert {"comfyui", "drawthings"} <= image_runner.ENGINES
