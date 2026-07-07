"""Tests for the GitHub read-only connector (P5b, docs/packets/020).

All tests run against a mocked HTTP transport. The connector's job is to map
GitHub's REST shape onto Kitty's signal store; this file pins that mapping.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import pytest

from gateway import signal_store
from gateway.connectors import github as github_module

# --- Fixtures ---------------------------------------------------------------


@pytest.fixture(autouse=True)
def isolate_signal_store(monkeypatch, tmp_path):
    """Keep tests away from live user data."""
    db_file = tmp_path / "kitty" / "kitty.db"
    monkeypatch.setattr(signal_store, "SIGNALS_DB_FILE", db_file, raising=False)


@dataclass
class _HttpScript:
    """A canned response sequence for the injected HTTP transport."""

    entries: list
    index: int = 0


def _scripted_http_get(script: _HttpScript):
    calls: list[tuple[str, dict[str, str], dict[str, str]]] = []

    def _get(url: str, params: dict[str, str], headers: dict[str, str]) -> dict[str, Any]:
        calls.append((url, dict(params), dict(headers)))
        if script.index >= len(script.entries):
            raise AssertionError(f"script exhausted at call #{len(calls)}: {url} {params}")
        response = script.entries[script.index]
        script.index += 1
        if isinstance(response, Exception):
            raise response
        return response

    _get.calls = calls  # type: ignore[attr-defined]
    return _get


# --- Helpers ----------------------------------------------------------------


def _prs_response(prs: list[dict]) -> dict[str, Any]:
    return {"items": prs}


def _pr(number: int, sha: str = "abcdef", title: str = "Test PR", state: str = "open") -> dict:
    return {
        "number": number,
        "title": title,
        "state": state,
        "draft": False,
        "html_url": f"https://github.com/jacob202/kitty/pull/{number}",
        "user": {"login": "jacob202"},
        "head": {"sha": sha},
    }


def _checks_response(checks: list[dict]) -> dict[str, Any]:
    return {"check_runs": checks}


def _check(name: str, status: str, conclusion: str | None = None) -> dict:
    return {
        "name": name,
        "status": status,
        "conclusion": conclusion,
        "html_url": "https://github.com/jacob202/kitty/actions/runs/123",
    }


def _reviews_response(reviews: list[dict]) -> dict[str, Any]:
    return {"items": reviews}


def _review(id_: int, state: str) -> dict:
    return {
        "id": id_,
        "state": state,
        "user": {"login": "reviewer"},
        "html_url": f"https://github.com/jacob202/kitty/pull/1#pullrequestreview-{id_}",
    }


# --- Tests ------------------------------------------------------------------


def test_auth_headers():
    script = _HttpScript([_prs_response([])])
    connector = github_module.GithubConnector(
        token="my-token",
        repos=["jacob202/kitty"],
        http_get=_scripted_http_get(script),
    )
    result = connector.poll()
    assert result.new == 0

    _get: Any = connector._http_get
    assert len(_get.calls) == 1

    url, params, headers = _get.calls[0]
    assert headers["Authorization"] == "Bearer my-token"
    assert "application/vnd.github.v3+json" in headers["Accept"]


def test_auth_error_missing_token():
    connector = github_module.GithubConnector(
        token="",
        repos=["jacob202/kitty"],
    )
    with pytest.raises(github_module.GithubAuthError, match="no token"):
        connector.poll()


def test_poll_success():
    script = _HttpScript([
        # /pulls
        _prs_response([_pr(114, "sha114", "Tailnet Card")]),
        # /check-runs for sha114
        _checks_response([_check("pytest", "completed", "success")]),
        # /reviews for PR 114
        _reviews_response([_review(999, "APPROVED")]),
    ])
    connector = github_module.GithubConnector(
        token="fake",
        repos=["jacob202/kitty"],
        http_get=_scripted_http_get(script),
    )
    result = connector.poll()
    assert result.new == 3  # PR, Check, Review
    assert result.deduped == 0
    assert result.errors == 0

    signals = signal_store.list_recent(limit=10)
    assert len(signals) == 3

    # Assert PR signal
    pr_sig = next(s for s in signals if s["kind"] == "github.pr")
    assert pr_sig["payload"]["pr_number"] == 114
    assert pr_sig["payload"]["state"] == "open"
    assert pr_sig["dedupe_key"] == "github:pr:jacob202/kitty:114:state:open"

    # Assert Check signal
    chk_sig = next(s for s in signals if s["kind"] == "github.check")
    assert chk_sig["payload"]["check_name"] == "pytest"
    assert chk_sig["payload"]["conclusion"] == "success"

    # Assert Review signal
    rev_sig = next(s for s in signals if s["kind"] == "github.review")
    assert rev_sig["payload"]["comment_id"] == 999
    assert rev_sig["payload"]["state"] == "APPROVED"


def test_poll_deduplicates():
    script = _HttpScript([
        _prs_response([_pr(114)]),
        _checks_response([_check("pytest", "completed", "success")]),
        _reviews_response([_review(999, "APPROVED")]),
    ])
    connector = github_module.GithubConnector(
        token="fake",
        repos=["jacob202/kitty"],
        http_get=_scripted_http_get(script),
    )
    # Run once
    res1 = connector.poll()
    assert res1.new == 3
    assert res1.deduped == 0

    # Reset script and run again
    script.index = 0
    res2 = connector.poll()
    assert res2.new == 0
    assert res2.deduped == 3  # All duplicate keys


def test_poll_handles_partial_failures():
    # If check-runs fail, it still fetches reviews and emits the PR.
    script = _HttpScript([
        _prs_response([_pr(114)]),
        github_module.GithubTransportError("500 API Error"),  # Checks fail
        _reviews_response([_review(999, "CHANGES_REQUESTED")]),
    ])
    connector = github_module.GithubConnector(
        token="fake",
        repos=["jacob202/kitty"],
        http_get=_scripted_http_get(script),
    )
    res = connector.poll()
    assert res.errors == 1  # The checks request failed
    assert res.new == 2     # Emitted PR and Review signals

    signals = signal_store.list_recent(limit=10)
    kinds = [s["kind"] for s in signals]
    assert "github.pr" in kinds
    assert "github.review" in kinds
    assert "github.check" not in kinds


def test_poll_now_unconfigured():
    # poll_now returns silently when token missing
    import os
    if "GITHUB_TOKEN" in os.environ:
        del os.environ["GITHUB_TOKEN"]

    res = github_module.poll_now()
    assert res["skipped"] == "unconfigured"
    assert res["errors"] == 0
