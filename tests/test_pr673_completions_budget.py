import json

import pytest
from fastapi import HTTPException

from gateway.routes import completions


def test_final_model_visible_payload_is_bounded_and_preserves_current_user() -> None:
    current = {"role": "user", "content": "CURRENT 🧠 question"}
    history = [
        {"role": "user", "content": "old user " * 80},
        {"role": "assistant", "content": "old assistant " * 80},
        current,
    ]
    final, warnings = completions._fit_final_model_messages(
        bundle_system="bundle " * 100,
        runtime_system="runtime " * 40,
        tool_system="tool guard " * 20,
        messages=history,
        token_cap=700,
    )
    units = sum(
        len(json.dumps(message, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
        for message in final
    )
    assert units <= 700
    assert final[-1] == current
    assert warnings


def test_final_budget_never_truncates_required_runtime_truth() -> None:
    current = {"role": "user", "content": "CURRENT question"}
    with pytest.raises(HTTPException) as excinfo:
        completions._fit_final_model_messages(
            bundle_system="",
            runtime_system="RUNTIME-TRUTH " * 40,
            tool_system="TOOL-GUARD",
            messages=[current],
            token_cap=180,
        )
    assert getattr(excinfo.value, "status_code", None) == 413
    assert "runtime" in str(getattr(excinfo.value, "detail", "")).lower()



def test_final_budget_preserves_post_user_tool_continuation() -> None:
    current = {"role": "user", "content": "Use the weather tool"}
    assistant_call = {
        "role": "assistant",
        "content": None,
        "tool_calls": [{
            "id": "call-1",
            "type": "function",
            "function": {"name": "weather", "arguments": "{}"},
        }],
    }
    tool_result = {"role": "tool", "tool_call_id": "call-1", "content": "sunny"}
    final, _ = completions._fit_final_model_messages(
        bundle_system="",
        runtime_system="",
        tool_system="",
        messages=[current, assistant_call, tool_result],
        token_cap=1000,
    )
    assert final == [current, assistant_call, tool_result]


def test_final_budget_keeps_historical_tool_exchange_atomic_when_trimming() -> None:
    assistant_call = {
        "role": "assistant",
        "content": None,
        "tool_calls": [{
            "id": "old-call",
            "type": "function",
            "function": {"name": "lookup", "arguments": "x" * 400},
        }],
    }
    tool_result = {"role": "tool", "tool_call_id": "old-call", "content": "ok"}
    current = {"role": "user", "content": "CURRENT"}
    cap = (
        completions._message_budget_units(current)
        + completions._message_budget_units(tool_result)
        + 10
    )
    final, warnings = completions._fit_final_model_messages(
        bundle_system="",
        runtime_system="",
        tool_system="",
        messages=[assistant_call, tool_result, current],
        token_cap=cap,
    )
    assert final == [current]
    assert warnings == ["context_budget:history: dropped 2 older message(s)"]

def test_compact_runtime_truth_keeps_required_sections_without_redundant_provenance() -> None:
    from gateway.runtime_manifest import compact_runtime_context

    def fact(value, *, reason=None, state="available"):
        row = {
            "state": state,
            "value": value,
            "source": "PROVENANCE-NOISE",
            "observed_at": "2026-08-29T00:00:00Z",
            "valid_until": "2026-08-29T00:00:15Z",
        }
        if reason is not None:
            row["reason"] = reason
        return row

    manifest = {
        "revision": "abc123",
        "generated_at": "2026-08-29T00:00:00Z",
        "valid_until": "2026-08-29T00:00:15Z",
        "application": {"name": "Kitty", "version": fact("1"), "build_commit": "deadbeef", "environment": "test"},
        "clock": fact({"current_time": "now", "timezone": "UTC"}),
        "context": {"active_project": fact({"id": 7, "name": "Keep Me"}), "repository": fact({"branch": "main"})},
        "execution": {"builder": fact({"initiatives": [{"id": 1}], "queue": {"pending": 2}})},
        "inference": {"routing_mode": "gateway", "available_models": fact(["model-a"]), "execution_location": "local"},
        "tools": fact([{"id": "TOOL-NOISE"}]),
        "connections": {"gateway": fact("CONNECTION-NOISE", reason="connection unavailable", state="unavailable")},
        "approvals": fact({"policy": "APPROVAL-NOISE"}, reason="approval policy degraded", state="degraded"),
    }

    rendered = compact_runtime_context(manifest)
    assert "Keep Me" in rendered
    assert "model-a" in rendered
    assert "PROVENANCE-NOISE" not in rendered
    assert "TOOL-NOISE" in rendered
    assert "connection unavailable" in rendered
    assert "approval policy degraded" in rendered
    assert "CONNECTION-NOISE" not in rendered
    assert "APPROVAL-NOISE" not in rendered
