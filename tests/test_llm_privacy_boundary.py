"""D10 — privacy boundary in the LLM router.

These tests are the contract. The boundary must reject cloud routing for
content classes that D10 marks local-only, regardless of which provider the
caller names. They are pure-function tests: no network, no FastAPI client,
no real models. They run in well under a second.
"""

from __future__ import annotations

import pytest

from gateway.llm_client import (
    PRIVACY_LOCAL_ONLY,
    PrivacyBoundaryError,
    call_llm,
    enforce_privacy_boundary,
)


def test_local_only_classes_are_listed():
    """The set is the contract for every class that must stay on the Mac."""
    assert "journal" in PRIVACY_LOCAL_ONLY
    assert "mail_body" in PRIVACY_LOCAL_ONLY
    assert "health_admin" in PRIVACY_LOCAL_ONLY
    assert "knowledge_document" in PRIVACY_LOCAL_ONLY


def test_enforce_rejects_journal_on_cloud():
    with pytest.raises(PrivacyBoundaryError) as exc:
        enforce_privacy_boundary("cloud_ok", "journal")
    assert "journal" in str(exc.value)
    assert "D10" in str(exc.value)


def test_enforce_rejects_mail_body_on_cloud():
    with pytest.raises(PrivacyBoundaryError):
        enforce_privacy_boundary("cloud_ok", "mail_body")


def test_enforce_rejects_health_admin_on_cloud():
    with pytest.raises(PrivacyBoundaryError):
        enforce_privacy_boundary("cloud_ok", "health_admin")


def test_enforce_rejects_knowledge_documents_on_cloud():
    with pytest.raises(PrivacyBoundaryError):
        enforce_privacy_boundary("cloud_ok", "knowledge_document")


def test_enforce_allows_journal_on_local():
    enforce_privacy_boundary("local", "journal")


def test_enforce_allows_non_private_class_on_cloud():
    """Calendar, todo, chat are cloud-permitted by D10."""
    for cls in ("calendar", "todo", "chat"):
        enforce_privacy_boundary("cloud_ok", cls)


def test_enforce_allows_cloud_with_no_class():
    """Legacy call sites that don't tag content_class keep permissive behavior."""
    enforce_privacy_boundary("cloud_ok", None)


def test_call_llm_rejects_journal_cloud_at_boundary(monkeypatch):
    """call_llm must raise PrivacyBoundaryError before contacting any provider.

    We monkeypatch _post to raise loudly if the boundary check ever leaks
    through — that would be a regression on the contract.
    """

    def _explode(*_args, **_kwargs):
        raise AssertionError("provider was contacted; boundary failed to reject")

    monkeypatch.setattr("gateway.llm_client._post", _explode)

    with pytest.raises(PrivacyBoundaryError):
        call_llm(
            [{"role": "user", "content": "test"}],
            privacy_tier="cloud_ok",
            content_class="journal",
        )


def test_call_llm_passes_through_when_local():
    """Journal content + privacy_tier=local must reach the provider chain."""
    captured: dict = {}

    def _fake_post(url, **kwargs):
        captured["url"] = url
        import requests

        resp = requests.Response()
        resp.status_code = 200
        resp._content = (
            b'{"choices":[{"message":{"role":"assistant","content":"ok"}}],'
            b'"model":"test","usage":{"prompt_tokens":1,"completion_tokens":1}}'
        )
        return resp

    monkey = __import__("pytest").MonkeyPatch()
    try:
        monkey.setattr("gateway.llm_client._post", _fake_post)
        out = call_llm(
            [{"role": "user", "content": "private"}],
            privacy_tier="local",
            content_class="journal",
        )
        assert out == "ok"
    finally:
        monkey.undo()
