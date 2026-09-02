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


def test_extract_context_references_leaves_marker_free_text_byte_for_byte():
    text = "keep   me\n\n\n\nexactly    as-is  "

    clean, refs = context_references.extract_context_references(text)

    assert clean == text
    assert refs == []


def test_resolves_project_artifact_and_chat_into_bounded_context(monkeypatch, tmp_path):
    artifact_file = tmp_path / "report.md"
    artifact_file.write_text("# Result\nThe experiment worked.")

    monkeypatch.setattr(
        context_references.artifact_store,
        "_hash_file",
        lambda path: ("hash-1", 42),
    )
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
        "content_hash": "hash-1",
        "size_bytes": 42,
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


def test_artifact_block_flags_content_that_changed_on_disk(monkeypatch, tmp_path):
    artifact_file = tmp_path / "report.md"
    artifact_file.write_text("# Result\nThe experiment worked.")

    monkeypatch.setattr(context_references.artifact_store, "get_artifact", lambda artifact_id: {
        "id": artifact_id,
        "display_name": "report.md",
        "media_type": "text/plain",
        "state": "ready",
        "storage_uri": str(artifact_file),
        "content_hash": "stale-hash",
        "size_bytes": artifact_file.stat().st_size,
    })

    _, warnings = context_references.resolve_context_references([
        context_references.ContextReference(kind="artifact", ref_id="artifact_1"),
    ])

    assert any("changed on disk" in warning for warning in warnings)


def test_artifact_block_rejects_undecodable_text(monkeypatch, tmp_path):
    artifact_file = tmp_path / "report.bin"
    artifact_file.write_bytes(b"\xff\xfe\xfa\x00not utf8")
    current_hash, current_size = context_references.artifact_store._hash_file(artifact_file)

    monkeypatch.setattr(context_references.artifact_store, "get_artifact", lambda artifact_id: {
        "id": artifact_id,
        "display_name": "report.bin",
        "media_type": "text/plain",
        "state": "ready",
        "storage_uri": str(artifact_file),
        "content_hash": current_hash,
        "size_bytes": current_size,
    })

    _, warnings = context_references.resolve_context_references([
        context_references.ContextReference(kind="artifact", ref_id="artifact_1"),
    ])

    assert any("not valid UTF-8" in warning for warning in warnings)


def test_chat_block_prefers_lifecycle_ledger_over_stale_blob(monkeypatch):
    monkeypatch.setattr(context_references.chats_store, "get_chat", lambda chat_id: {
        "id": chat_id,
        "title": "Earlier design discussion",
        "messages": [
            {"role": "user", "content": "stale blob only"},
        ],
    })
    monkeypatch.setattr(context_references.chat_lifecycle, "list_conversation", lambda conversation_id: {
        "conversation": {},
        "turns": [
            {
                "messages": [
                    {"role": "user", "content": "recovered user turn", "status": "complete"},
                    {"role": "assistant", "content": "recovered answer", "status": "complete"},
                    {"role": "assistant", "content": "partial junk", "status": "interrupted"},
                ],
            },
        ],
    })

    block, warnings = context_references.resolve_context_references([
        context_references.ContextReference(kind="chat", ref_id="chat-9"),
    ])

    assert warnings == []
    assert "recovered user turn" in block
    assert "recovered answer" in block
    assert "stale blob only" not in block
    assert "partial junk" not in block


def test_chat_block_falls_back_to_blob_without_ledger(monkeypatch):
    def missing(conversation_id):
        raise context_references.chat_lifecycle.ChatLifecycleError(
            f"conversation {conversation_id} does not exist"
        )

    monkeypatch.setattr(context_references.chat_lifecycle, "list_conversation", missing)
    monkeypatch.setattr(context_references.chats_store, "get_chat", lambda chat_id: {
        "id": chat_id,
        "title": "Blob only",
        "messages": [{"role": "user", "content": "blob message"}],
    })

    block, warnings = context_references.resolve_context_references([
        context_references.ContextReference(kind="chat", ref_id="chat-9"),
    ])

    assert warnings == []
    assert "blob message" in block
