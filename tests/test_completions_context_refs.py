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

    clean_messages, clean_user_text, raw_user_text, warnings = (
        completions._prepare_explicit_context(messages)
    )

    assert raw_user_text.endswith("<!-- kitty-context:project:7 -->")
    assert clean_user_text == "compare @current"
    assert "kitty-context" not in str(clean_messages)
    assert clean_messages[0]["content"] == "old question @old"
    assert clean_messages[-1]["content"].startswith(
        "## Explicit context\nProject: current\n\ncompare @current"
    )
    assert warnings == []
    assert len(calls) == 1
    assert calls[0][0].kind == "project"
    assert calls[0][0].ref_id == "7"


def test_prepare_explicit_context_keeps_non_user_content_byte_for_byte():
    assistant = {
        "role": "assistant",
        "content": "line one\n\n<!-- kitty-context:project:1 -->\n\n\n\nline two   ",
    }
    tool = {"role": "tool", "tool_call_id": "t1", "content": "<!-- kitty-context:artifact:a1 -->"}

    clean_messages, _, _, warnings = completions._prepare_explicit_context(
        [assistant, tool, {"role": "user", "content": "hello"}]
    )

    assert clean_messages[0]["content"] == assistant["content"]
    assert clean_messages[1]["content"] == tool["content"]
    assert warnings == []


def test_prepare_explicit_context_merges_block_into_list_user_content(monkeypatch):
    monkeypatch.setattr(
        completions.context_references,
        "resolve_context_references",
        lambda refs: ("## Explicit context\nArtifact: report", []),
    )
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": "data:image/png;base64,AAA"}},
                {"type": "text", "text": "what is this @report\n\n<!-- kitty-context:artifact:artifact_1 -->"},
            ],
        },
    ]

    clean_messages, clean_user_text, raw_user_text, warnings = (
        completions._prepare_explicit_context(messages)
    )

    content = clean_messages[0]["content"]
    assert content[0]["type"] == "image_url"
    assert content[-1] == {"type": "text", "text": "## Explicit context\nArtifact: report"}
    assert clean_user_text == "what is this @report"
    assert raw_user_text.endswith("<!-- kitty-context:artifact:artifact_1 -->")
    assert warnings == []
