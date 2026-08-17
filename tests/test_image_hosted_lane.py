"""The hosted image lane — the only one that spends money."""

from __future__ import annotations

import asyncio

import pytest

from gateway import image_runner


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv("KITTY_IMAGE_PAID_ENABLED", raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")


def test_paid_generation_is_off_until_it_is_switched_on():
    """Jacob retired the last paid image provider over cost. Nothing here spends
    until he says so, and the reason has to carry the price and the switch."""
    available, reason = image_runner.openrouter_images_available()

    assert available is False
    assert "billed" in reason.lower()
    assert "KITTY_IMAGE_PAID_ENABLED" in reason


def test_the_switch_turns_it_on(monkeypatch):
    monkeypatch.setenv("KITTY_IMAGE_PAID_ENABLED", "1")

    assert image_runner.openrouter_images_available() == (True, "")


def test_the_switch_alone_is_not_enough_without_a_key(monkeypatch):
    monkeypatch.setenv("KITTY_IMAGE_PAID_ENABLED", "1")
    monkeypatch.setenv("OPENROUTER_API_KEY", "")

    available, reason = image_runner.openrouter_images_available()

    assert available is False
    assert "OPENROUTER_API_KEY" in reason


def test_a_disabled_lane_refuses_before_it_can_charge():
    """The refusal must land before the HTTP call, not after."""
    with pytest.raises(image_runner.ImageRunnerError) as excinfo:
        asyncio.run(image_runner.run("openrouter", "a pear"))

    assert "off" in str(excinfo.value)


def test_openrouter_is_a_dispatchable_engine():
    assert "openrouter" in image_runner.ENGINES
    assert {"comfyui", "drawthings"} <= image_runner.ENGINES


def test_flux_is_off_until_the_same_switch_is_thrown(monkeypatch):
    monkeypatch.setenv("BFL_API_KEY", "test-key")

    available, reason = image_runner.flux_images_available()

    assert available is False
    assert "billed" in reason.lower()


def test_flux_needs_its_own_key(monkeypatch):
    monkeypatch.setenv("KITTY_IMAGE_PAID_ENABLED", "1")
    monkeypatch.setenv("BFL_API_KEY", "")

    available, reason = image_runner.flux_images_available()

    assert available is False
    assert "BFL_API_KEY" in reason


def test_flux_is_a_dispatchable_engine():
    assert "flux" in image_runner.ENGINES
