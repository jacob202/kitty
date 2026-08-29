from __future__ import annotations

import pytest

from gateway import memory_graph

pytestmark = pytest.mark.asyncio


async def test_explicit_memory_adapter_preserves_provenance(monkeypatch):
    monkeypatch.setattr(
        "gateway.explicit_memory.search",
        lambda query, limit=5: [
            {
                "id": "exp_1",
                "text": "Use light mode now",
                "memory_key": "ui.theme",
                "namespace": "preferences",
                "source_kind": "user_correction",
                "source_ref": "conversation:c2",
                "sensitivity": "normal",
                "pinned": True,
                "truth_confidence": 1.0,
                "created_at": "2026-08-23T10:00:00+00:00",
                "updated_at": "2026-08-23T10:00:00+00:00",
            }
        ],
    )
    item = (await memory_graph.ExplicitMemoryAdapter().fetch("theme"))[0]

    assert item.source is memory_graph.Source.EXPLICIT_MEMORY
    assert item.text == "Use light mode now"
    assert item.score is None
    assert item.metadata["id"] == "exp_1"
    assert item.metadata["source_kind"] == "user_correction"
    assert item.metadata["source_ref"] == "conversation:c2"
    assert item.metadata["truth_confidence"] == 1.0
    assert item.metadata["pinned"] is True


async def test_project_adapter_reads_project_owner_without_copying_truth(monkeypatch):
    monkeypatch.setattr(
        "gateway.project_store.list_projects",
        lambda status=None: [
            {
                "id": 7,
                "name": "Kitty",
                "kind": "code",
                "status": "active",
                "summary": "Current canonical project summary",
                "open_questions": ["one"],
                "next_actions": ["ship #552"],
                "last_touched": 123.0,
            }
        ],
    )
    [item] = await memory_graph.ProjectAdapter().fetch("Kitty project")
    assert item.source is memory_graph.Source.PROJECTS
    assert "Current canonical project summary" in item.text
    assert "ship #552" in item.text
    assert item.metadata["project_id"] == 7
    assert item.metadata["owner"] == "project_store"


async def test_default_memory_graph_has_only_real_population_paths():
    adapters = memory_graph._default_adapters()
    names = [adapter.name for adapter in adapters]

    assert names[:3] == ["projects", "explicit_memory", "memory"]
    assert "facts" not in names
    assert any(isinstance(adapter, memory_graph.ProjectAdapter) for adapter in adapters)
    assert any(isinstance(adapter, memory_graph.ExplicitMemoryAdapter) for adapter in adapters)
    assert not any(isinstance(adapter, memory_graph.WeaveAdapter) for adapter in adapters)


async def test_project_truth_renders_before_stale_semantic_memory():
    results = {
        "projects": [
            memory_graph.Item(
                text="Kitty project status: #552 is current",
                source=memory_graph.Source.PROJECTS,
            )
        ],
        "memory": [
            memory_graph.Item(
                text="Old recollection: #552 is not started",
                source=memory_graph.Source.MEMORY,
            )
        ],
    }
    rendered = memory_graph._format_unified_items(results, query="Kitty #552 status")
    assert rendered.index("Kitty project status") < rendered.index("Old recollection")


async def test_remember_tool_writes_governed_explicit_memory(monkeypatch):
    from gateway.routes import tool_server

    captured = {}

    def fake_remember(text, **kwargs):
        captured.update(text=text, **kwargs)
        return {
            "id": "exp_new",
            "namespace": kwargs["namespace"],
            "source_kind": kwargs["source_kind"],
        }

    monkeypatch.setattr("gateway.explicit_memory.remember", fake_remember)
    body = tool_server.RememberRequest(
        text="Use light mode now",
        namespace="preferences",
        memory_key="ui.theme",
        supersedes_id="exp_old",
        source_ref="conversation:c2",
    )
    result = tool_server.remember(body)

    assert result["stored"] is True
    assert result["memory_id"] == "exp_new"
    assert result["source_kind"] == "user_correction"
    assert captured["memory_key"] == "ui.theme"
    assert captured["supersedes_id"] == "exp_old"
    assert captured["source_ref"] == "conversation:c2"


async def test_memory_search_tool_exposes_explicit_provenance(monkeypatch):
    from gateway.routes import tool_server

    async def fake_context(query, *, _record=True):
        return "## Explicit Memory\n- Use light mode now"

    monkeypatch.setattr("gateway.memory_graph.unified_context", fake_context)
    monkeypatch.setattr(
        "gateway.explicit_memory.search",
        lambda query, limit=5: [
            {
                "id": "exp_new",
                "text": "Use light mode now",
                "memory_key": "ui.theme",
                "namespace": "preferences",
                "source_kind": "user_correction",
                "source_ref": "conversation:c2",
            }
        ],
    )
    result = await tool_server.search_memory("theme", limit=5)
    assert result["explicit_memories"] == [
        {
            "id": "exp_new",
            "text": "Use light mode now",
            "memory_key": "ui.theme",
            "namespace": "preferences",
            "source_kind": "user_correction",
            "source_ref": "conversation:c2",
        }
    ]


async def test_memories_route_keeps_explicit_memory_when_mem0_is_down(monkeypatch):
    from gateway import memory
    from gateway.routes import memories as memories_route

    monkeypatch.setattr(
        "gateway.explicit_memory.list_memories",
        lambda namespace=None, limit=50: [
            {
                "id": "exp_1",
                "text": "I prefer dark mode",
                "namespace": "preferences",
                "source_kind": "user_explicit",
                "source_ref": "conversation:c1",
                "memory_key": "ui.theme",
                "status": "active",
            }
        ],
    )
    monkeypatch.setattr(
        memory,
        "list_memories",
        lambda **kwargs: (_ for _ in ()).throw(memory.MemoryError("ollama down")),
    )
    result = await memories_route.list_memories(namespace=None, limit=50)
    assert [row["id"] for row in result["memories"]] == ["exp_1"]
    assert result["memories"][0]["metadata"]["source_kind"] == "user_explicit"
    assert result["warnings"] == ["semantic_memory: ollama down"]


async def test_memories_route_forgets_explicit_id_without_mem0(monkeypatch):
    from gateway import undo_journal
    from gateway.routes import memories as memories_route

    called = []
    monkeypatch.setattr(
        undo_journal,
        "forget_memory_with_undo",
        lambda memory_id: called.append(memory_id) or "undo_1",
    )
    result = await memories_route.delete_memory("exp_123")
    assert result == {"deleted": True, "memory_id": "exp_123"}
    assert called == ["exp_123"]


async def test_session_memory_retains_conversation_and_time_lineage(tmp_path, monkeypatch):
    from gateway import memory

    captured = {}
    monkeypatch.setattr(memory, "SESSION_CONSOLIDATION_LOG", tmp_path / "sessions.jsonl")

    def fake_add(text, namespace="facts", metadata=None):
        captured.update(text=text, namespace=namespace, metadata=metadata)
        return True

    monkeypatch.setattr(memory, "add_memory", fake_add)
    messages = [
        {
            "role": "user",
            "content": "Remember this project decision",
            "timestamp": "2026-08-23T10:00:00Z",
        },
        {
            "role": "assistant",
            "content": "Got it",
            "timestamp": "2026-08-23T10:01:00Z",
        },
    ]
    assert memory.consolidate_session("chat-42", messages) is True
    metadata = captured["metadata"]
    assert metadata["source_conversation_id"] == "chat-42"
    assert metadata["source_started_at"] == "2026-08-23T10:00:00Z"
    assert metadata["source_ended_at"] == "2026-08-23T10:01:00Z"
    assert metadata["consolidated_at"]

    import json

    record = json.loads(memory.SESSION_CONSOLIDATION_LOG.read_text().strip())
    assert record["source_conversation_id"] == "chat-42"
    assert record["source_started_at"] == "2026-08-23T10:00:00Z"
    assert record["source_ended_at"] == "2026-08-23T10:01:00Z"


async def test_doctor_reports_actual_semantic_memory_degradation(monkeypatch):
    from gateway import doctor, memory

    def unavailable():
        raise memory.MemoryError("ollama embedder unavailable")

    monkeypatch.setattr(memory, "_probe_memory_backend", unavailable)
    [check] = doctor._check_mem0({"MEM0_API_KEY": "misleading-hosted-key"})

    assert check.level == "WARN"
    assert check.name == "store:mem0"
    assert "semantic memory unavailable" in check.detail.lower()
    assert "ollama embedder unavailable" in check.detail.lower()
    assert "explicit memory" in check.detail.lower()


async def test_doctor_passes_only_when_kitty_mem0_initializes(monkeypatch):
    from gateway import doctor, memory

    monkeypatch.setattr(memory, "_probe_memory_backend", lambda: object())
    [check] = doctor._check_mem0({})
    assert check.level == "PASS"
    assert "semantic memory available" in check.detail.lower()


async def test_remember_tool_cannot_masquerade_as_project_truth():
    from pydantic import ValidationError

    from gateway.routes import tool_server

    with pytest.raises(ValidationError):
        tool_server.RememberRequest(
            text="Kitty is done",
            namespace="projects",
        )


async def test_semantic_memory_probe_does_not_mutate_runtime_cache(monkeypatch):
    from gateway import memory

    marker = RuntimeError("cached old failure")
    monkeypatch.setattr(memory, "_MEMORY_INSTANCE", None)
    monkeypatch.setattr(memory, "_MEMORY_INIT_FAILED", True)
    monkeypatch.setattr(memory, "_MEMORY_INIT_ERROR", marker)
    monkeypatch.setattr(memory, "_build_mem0_config", lambda: {"test": True})
    monkeypatch.setattr(memory._Mem0Memory, "from_config", lambda config: object())

    assert memory._probe_memory_backend() is not None
    assert memory._MEMORY_INSTANCE is None
    assert memory._MEMORY_INIT_FAILED is True
    assert memory._MEMORY_INIT_ERROR is marker
