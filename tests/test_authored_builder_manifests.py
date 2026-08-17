from __future__ import annotations

import json
from pathlib import Path

from gateway import builder_initiative as bi

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_DIR = ROOT / "data" / "kittybuilder" / "manifests"


def _load(name: str) -> dict:
    return json.loads((MANIFEST_DIR / name).read_text(encoding="utf-8"))


def test_cheap_hardening_manifest_validates_against_builder_contract() -> None:
    payload = _load("builder-cheap-hardening-20260816.json")

    assert payload["initiative_id"] == "builder-cheap-hardening-20260816-v3"
    assert len(payload["packets"]) == 40
    assert bi.validate_manifest(payload) == []


def test_home_stretch_manifest_validates_against_builder_contract() -> None:
    payload = _load("home-stretch-cheap-execution-20260816.json")

    assert payload["initiative_id"] == "home-stretch-cheap-execution-20260816"
    assert len(payload["packets"]) == 15
    assert bi.validate_manifest(payload) == []


def test_authored_packet_ids_are_unique_across_both_initiatives() -> None:
    manifests = [
        _load("builder-cheap-hardening-20260816.json"),
        _load("home-stretch-cheap-execution-20260816.json"),
    ]
    ids = [packet["id"] for manifest in manifests for packet in manifest["packets"]]

    assert len(ids) == 55
    assert len(set(ids)) == len(ids)


def test_home_stretch_is_explicitly_gated_behind_routing_bootstrap() -> None:
    payload = _load("home-stretch-cheap-execution-20260816.json")

    assert "DO NOT APPLY" in payload["description"]
    assert "supervisor-route-aware-launch" in payload["description"]


def test_authored_paid_packet_routes_use_canonical_openrouter_slugs() -> None:
    manifests = [
        _load("builder-cheap-hardening-20260816.json"),
        _load("home-stretch-cheap-execution-20260816.json"),
    ]

    for manifest in manifests:
        for packet in manifest["packets"]:
            routing = packet["policy"]["routing"]
            assert routing["provider"] == "openrouter"
            assert routing["model"].startswith("openrouter/")
