"""Tests for scripts/image_lab_acceptance_scene.py.

Verifies the two-character plan this script builds reaches the real
/studio/generate dispatch path — including real (unmocked) recipe
auto-routing — and produces exactly two ordered CompiledReference entries
with the expected left/right cast_slot assignment. Only the network boundary
(httpx.AsyncClient) is faked, so a passing test here is real evidence the
script would reach the hosted FLUX.2 transport correctly with a live
BFL_API_KEY — not just that its own code runs.
"""

from __future__ import annotations

import json as _json
from pathlib import Path

import pytest
from PIL import Image

from scripts.image_lab_acceptance_scene import build_two_character_plan


@pytest.fixture(autouse=True)
def _scratch_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    import gateway.paths as paths

    db_file = tmp_path / "kitty.db"
    monkeypatch.setattr(paths, "KITTY_DB_FILE", db_file)
    monkeypatch.setattr("gateway.artifact_store.ARTIFACTS_DB_FILE", db_file)
    monkeypatch.setenv("KITTY_IMAGE_PAID_ENABLED", "1")
    monkeypatch.setenv("BFL_API_KEY", "test-bfl-key")


class _FakeClient:
    def __init__(self, submit_json, poll_json, sample_bytes=b"fake-png-bytes"):
        self.submit_json = submit_json
        self.poll_json = poll_json
        self.sample_bytes = sample_bytes
        self.posted_payload = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def post(self, url, *, headers=None, json=None):
        self.posted_payload = json
        from types import SimpleNamespace

        resp = SimpleNamespace()
        resp.status_code = 200
        resp.text = _json.dumps(self.submit_json)
        resp.json = lambda: self.submit_json
        return resp

    async def get(self, url, *, headers=None):
        from types import SimpleNamespace

        resp = SimpleNamespace()
        if url == self.submit_json.get("polling_url"):
            resp.status_code = 200
            resp.text = _json.dumps(self.poll_json)
            resp.json = lambda: self.poll_json
            resp.raise_for_status = lambda: None
            return resp
        resp.status_code = 200
        resp.text = ""
        resp.json = lambda: {}
        resp.content = self.sample_bytes
        resp.raise_for_status = lambda: None
        return resp


def _png(path: Path) -> None:
    Image.new("RGB", (64, 64), (10, 20, 30)).save(path)


def test_build_two_character_plan_persists_left_right_cast(tmp_path) -> None:
    from gateway.image_sessions import create_session

    ref_a = tmp_path / "a.png"
    ref_b = tmp_path / "b.png"
    _png(ref_a)
    _png(ref_b)

    session = create_session(title="acceptance scene test")
    plan = build_two_character_plan(
        session.session_id,
        prompt="two men on a pool deck in swim trunks, mid conversation",
        character_a_id="char-a",
        character_a_ref=ref_a,
        character_a_name="A",
        character_b_id="char-b",
        character_b_ref=ref_b,
        character_b_name="B",
    )

    assert plan.status.value == "approved"
    assert plan.operation == "txt2img"
    cast = plan.intent["cast"]
    assert [slot["position"] for slot in cast] == ["left", "right"]
    assert [slot["character_id"] for slot in cast] == ["char-a", "char-b"]


def test_build_two_character_plan_rejects_same_reference_photo(tmp_path) -> None:
    from gateway.image_sessions import create_session

    ref = tmp_path / "same.png"
    _png(ref)

    session = create_session(title="acceptance scene test")
    with pytest.raises(ValueError, match="same file"):
        build_two_character_plan(
            session.session_id,
            prompt="two men",
            character_a_id="char-a",
            character_a_ref=ref,
            character_b_id="char-b",
            character_b_ref=ref,
        )


def test_build_two_character_plan_rejects_missing_reference(tmp_path) -> None:
    from gateway.image_sessions import create_session

    session = create_session(title="acceptance scene test")
    with pytest.raises(FileNotFoundError):
        build_two_character_plan(
            session.session_id,
            prompt="two men",
            character_a_id="char-a",
            character_a_ref=tmp_path / "missing.png",
            character_b_id="char-b",
            character_b_ref=tmp_path / "also-missing.png",
        )


@pytest.mark.asyncio
async def test_dispatch_reaches_flux2_with_two_ordered_references(
    tmp_path, monkeypatch
) -> None:
    """End-to-end through the real (unmocked) recipe router — only the
    network boundary is faked. Proves auto_route picks a two-character-
    capable FLUX.2 recipe and the compiler receives both references in
    left/right cast order.
    """
    from gateway.image_sessions import create_session
    from scripts.image_lab_acceptance_scene import _dispatch

    ref_a = tmp_path / "a.png"
    ref_b = tmp_path / "b.png"
    _png(ref_a)
    _png(ref_b)

    from gateway.image_recipes import seed_default_recipes

    seed_default_recipes()

    session = create_session(title="acceptance scene dispatch test")
    plan = build_two_character_plan(
        session.session_id,
        prompt="two men on a pool deck in swim trunks, mid conversation",
        character_a_id="char-a",
        character_a_ref=ref_a,
        character_a_name="A",
        character_b_id="char-b",
        character_b_ref=ref_b,
        character_b_name="B",
    )

    submit = {"polling_url": "https://api.bfl.ai/v1/poll/acceptance", "cost": 3.0}
    ready = {"status": "Ready", "result": {"sample": "https://cdn.bfl.ai/s/acceptance", "seed": 7}}
    client = _FakeClient(submit, ready)
    monkeypatch.setattr("httpx.AsyncClient", lambda *a, **k: client)

    await _dispatch(plan.plan_id, session.session_id, quality="fast")

    payload = client.posted_payload
    assert "input_image" in payload
    assert "input_image_2" in payload
    assert payload["prompt"].startswith("two men on a pool deck")
