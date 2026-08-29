import json

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
