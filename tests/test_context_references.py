from gateway import context_references


def test_extracts_hidden_refs_without_leaking_markers_into_user_text():
    text = (
        "Compare @kitty with @research-report.md\n\n"
        "<!-- kitty-context:project:7 -->\n"
        "<!-- kitty-context:artifact:artifact_1 -->"
    )

    clean, refs = context_references.extract_context_references(text)

    assert clean == "Compare @kitty with @research-report.md"
    assert refs == [
        context_references.ContextReference(kind="project", ref_id="7"),
        context_references.ContextReference(kind="artifact", ref_id="artifact_1"),
    ]


def test_resolves_project_artifact_and_chat_into_bounded_context(monkeypatch, tmp_path):
    artifact_file = tmp_path / "report.md"
    artifact_file.write_text("# Result\nThe experiment worked.")

    monkeypatch.setattr(context_references.project_store, "get", lambda project_id: {
        "id": project_id,
        "name": "kitty",
        "kind": "code",
        "status": "active",
        "summary": "Build the Kitty product.",
        "next_actions": ["Ship the context picker"],
        "open_questions": ["How should mentions rank?"],
    })
    monkeypatch.setattr(context_references.artifact_store, "get_artifact", lambda artifact_id: {
        "id": artifact_id,
        "display_name": "research-report.md",
        "kind": "document",
        "media_type": "text/markdown",
        "state": "ready",
        "storage_uri": str(artifact_file),
        "size_bytes": artifact_file.stat().st_size,
    })
    monkeypatch.setattr(context_references.chats_store, "get_chat", lambda chat_id: {
        "id": chat_id,
        "title": "Earlier design discussion",
        "objective": "Choose the interaction model",
        "messages": [
            {"role": "user", "content": "Make Kitty easier to use."},
            {"role": "assistant", "content": "Use a capability launcher."},
        ],
    })

    block, warnings = context_references.resolve_context_references([
        context_references.ContextReference(kind="project", ref_id="7"),
        context_references.ContextReference(kind="artifact", ref_id="artifact_1"),
        context_references.ContextReference(kind="chat", ref_id="chat-9"),
    ])

    assert warnings == []
    assert "## Explicit context" in block
    assert "Project: kitty" in block
    assert "Ship the context picker" in block
    assert "Artifact: research-report.md" in block
    assert "The experiment worked." in block
    assert "Conversation: Earlier design discussion" in block
    assert "Use a capability launcher." in block
