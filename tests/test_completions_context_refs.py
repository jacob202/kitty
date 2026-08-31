from gateway.routes import completions


def test_prepare_explicit_context_resolves_only_latest_user_refs(monkeypatch):
    calls = []

    def resolve(refs):
        calls.append(refs)
        return "## Explicit context\nProject: current", []

    monkeypatch.setattr(completions.context_references, "resolve_context_references", resolve)
    messages = [
        {
            "role": "user",
            "content": "old question @old\n\n<!-- kitty-context:project:1 -->",
        },
        {"role": "assistant", "content": "old answer"},
        {
            "role": "user",
            "content": "compare @current\n\n<!-- kitty-context:project:7 -->",
        },
    ]

    clean_messages, clean_user_text, raw_user_text, block, warnings = (
        completions._prepare_explicit_context(messages)
    )

    assert raw_user_text.endswith("<!-- kitty-context:project:7 -->")
    assert clean_user_text == "compare @current"
    assert "kitty-context" not in str(clean_messages)
    assert clean_messages[0]["content"] == "old question @old"
    assert clean_messages[-1]["content"] == "compare @current"
    assert block == "## Explicit context\nProject: current"
    assert warnings == []
    assert len(calls) == 1
    assert calls[0][0].kind == "project"
    assert calls[0][0].ref_id == "7"
