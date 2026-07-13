"""Mem0 memory wrapper for Kitty Gateway."""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

from gateway.errors import StorageUnavailable
from gateway.paths import DATA_DIR


class MemoryError(StorageUnavailable):
    """Raised when the long-term memory backend is unavailable or invalid."""


logger = logging.getLogger("kitty.memory")

MEM0_DATA_DIR = DATA_DIR / "mem0"
USER_ID = "jacob"
MEMORY_LIST_ALL_LIMIT = 100_000

_MEM0_IMPORT_ERROR: ImportError | None = None
try:
    from mem0 import Memory as _Mem0Memory

    _MEM0_IMPORT_OK = True
except ImportError as exc:
    _Mem0Memory = None
    _MEM0_IMPORT_OK = False
    _MEM0_IMPORT_ERROR = exc
    logger.warning(
        "mem0ai is not installed; memory calls will fail until project requirements are installed"
    )

_MEMORY_INSTANCE = None
_MEMORY_INIT_FAILED = False
_MEMORY_INIT_ERROR: Exception | None = None

MEMORY_DEGRADED_CONTEXT = "## Memory\n- ⚠ Long-term memory is unavailable for this response."


def _memory_failure(
    operation: str,
    exc: Exception,
    **details: Any,
) -> MemoryError:
    return MemoryError(
        f"{operation} failed ({type(exc).__name__})",
        details={
            "operation": operation,
            "exception_type": type(exc).__name__,
            **details,
        },
    )


def _memory_rows(payload: Any, *, operation: str) -> list[dict]:
    """Validate Mem0's list response so malformed data is never false success."""
    if isinstance(payload, dict):
        if "results" not in payload:
            raise MemoryError(
                f"{operation} failed: backend response is missing 'results'",
                details={"operation": operation, "response_type": "dict"},
            )
        payload = payload["results"]

    if not isinstance(payload, list):
        raise MemoryError(
            f"{operation} failed: backend returned {type(payload).__name__}, expected list",
            details={
                "operation": operation,
                "response_type": type(payload).__name__,
            },
        )

    for index, item in enumerate(payload):
        if not isinstance(item, dict):
            raise MemoryError(
                f"{operation} failed: result {index} is {type(item).__name__}, expected dict",
                details={
                    "operation": operation,
                    "result_index": index,
                    "result_type": type(item).__name__,
                },
            )
    return payload


def _validate_namespace_results(
    memories: list[dict],
    namespace: str,
    *,
    operation: str,
) -> list[dict]:
    for index, item in enumerate(memories):
        metadata = item.get("metadata")
        if metadata is None:
            metadata = {}
        if not isinstance(metadata, dict):
            raise MemoryError(
                f"{operation} failed: result {index} metadata is "
                f"{type(metadata).__name__}, expected dict",
                details={
                    "operation": operation,
                    "result_index": index,
                    "metadata_type": type(metadata).__name__,
                },
            )
        if metadata.get("namespace") != namespace:
            raise MemoryError(
                f"{operation} failed: result {index} does not match "
                f"requested namespace {namespace!r}",
                details={
                    "operation": operation,
                    "result_index": index,
                    "namespace": namespace,
                },
            )
    return memories


def _memory_write_changed(payload: Any) -> bool:
    """Return whether Mem0 confirms an add/update/delete operation."""
    events = _memory_rows(payload, operation="memory add")
    changed = False
    for index, item in enumerate(events):
        event = item.get("event")
        if event in {"ADD", "UPDATE", "DELETE"}:
            changed = True
            continue
        if event == "NONE":
            continue
        raise MemoryError(
            f"memory add failed: result {index} has invalid event {event!r}",
            details={
                "operation": "memory add",
                "result_index": index,
                "event": event,
            },
        )
    return changed


def _build_mem0_config() -> dict:
    """Build Mem0 config at runtime using the routing system."""
    from gateway.llm_client import route_model

    model = os.environ.get("KITTY_MEMORY_MODEL") or route_model("memory context building")
    return {
        "llm": {
            "provider": "litellm",
            "config": {
                "model": model,
                "api_key": os.environ.get("OPENROUTER_API_KEY", ""),
            },
        },
        "embedder": {
            "provider": "ollama",
            "config": {
                "model": "nomic-embed-text",
                "ollama_base_url": "http://localhost:11434",
            },
        },
        "vector_store": {
            "provider": "chroma",
            "config": {
                "collection_name": "kitty_memory",
                "path": str(MEM0_DATA_DIR),
            },
        },
    }


def _get_memory():
    """Lazy-init Mem0, raising the cached cause while it is unavailable."""
    global _MEMORY_INSTANCE, _MEMORY_INIT_ERROR, _MEMORY_INIT_FAILED
    if not _MEM0_IMPORT_OK:
        raise MemoryError(
            "memory backend unavailable: mem0ai is not installed; install the project requirements",
            details={"operation": "memory initialization", "dependency": "mem0ai"},
        ) from _MEM0_IMPORT_ERROR
    if _MEMORY_INIT_FAILED:
        cause = _MEMORY_INIT_ERROR or RuntimeError(
            "previous initialization failure cause was not recorded"
        )
        raise _memory_failure(
            "memory initialization",
            cause,
            cached_failure=True,
        ) from _MEMORY_INIT_ERROR
    if _MEMORY_INSTANCE is not None:
        return _MEMORY_INSTANCE
    try:
        MEM0_DATA_DIR.mkdir(parents=True, exist_ok=True)
        config = _build_mem0_config()
        instance = _Mem0Memory.from_config(config)
        if instance is None:
            raise RuntimeError("Mem0 factory returned None")
        _MEMORY_INSTANCE = instance
        return _MEMORY_INSTANCE
    except Exception as exc:
        _MEMORY_INIT_FAILED = True
        _MEMORY_INIT_ERROR = exc
        raise _memory_failure("memory initialization", exc) from exc


def add_memory(text: str, namespace: str = "facts", metadata: Optional[dict] = None) -> bool:
    """Persist a memory entry and report whether Mem0 changed stored state."""
    mem = _get_memory()
    try:
        meta = {"namespace": namespace, **(metadata or {})}
        result = mem.add(text, user_id=USER_ID, metadata=meta)
    except Exception as exc:
        raise _memory_failure("memory add", exc, namespace=namespace) from exc
    if not _memory_write_changed(result):
        logger.info("Memory unchanged [%s]: %s", namespace, text[:80])
        return False
    logger.info("Memory stored [%s]: %s", namespace, text[:80])
    return True


def search_memory(query: str, limit: int = 5, namespace: Optional[str] = None) -> list[dict]:
    """Search memories relevant to query. Returns list of {memory, score} dicts.

    Raises MemoryError when the backend is unavailable, fails, or returns an
    invalid response. A successful search with no matches returns ``[]``.
    """
    mem = _get_memory()
    filters = {"user_id": USER_ID}
    if namespace:
        filters["namespace"] = namespace
    try:
        results = mem.search(query, filters=filters, limit=limit)
    except Exception as exc:
        raise _memory_failure(
            "memory search",
            exc,
            limit=limit,
            namespace=namespace,
        ) from exc

    memories = _memory_rows(results, operation="memory search")
    if namespace:
        return _validate_namespace_results(
            memories,
            namespace,
            operation="memory search",
        )
    return memories


def get_context_block(query: str, limit: int = 5) -> str:
    """Return a formatted context block to inject into the system prompt.

    A backend failure becomes an explicit degraded marker rather than the
    empty string used for a successful search with no matches.
    """
    try:
        memories = search_memory(query, limit=limit)
    except MemoryError as exc:
        logger.exception("Memory context degraded: %s", exc)
        return MEMORY_DEGRADED_CONTEXT
    if not memories:
        return ""
    lines = ["## What Kitty knows about Jacob (from memory):"]
    for m in memories:
        text = m.get("memory", m.get("text", ""))
        if text:
            lines.append(f"- {text}")
    return "\n".join(lines)


def list_memories(namespace: Optional[str] = None, limit: int = 50) -> list[dict]:
    """List all stored memories. Optionally filter by namespace.

    Raises MemoryError on unexpected backend failures.
    """
    mem = _get_memory()
    backend_limit = MEMORY_LIST_ALL_LIMIT if limit == 0 else limit
    try:
        if namespace:
            results = mem.get_all(
                user_id=USER_ID,
                filters={"namespace": namespace},
                limit=backend_limit,
            )
        else:
            results = mem.get_all(user_id=USER_ID, limit=backend_limit)
    except Exception as exc:
        raise _memory_failure(
            "memory list",
            exc,
            limit=limit,
            namespace=namespace,
        ) from exc

    memories = _memory_rows(results, operation="memory list")
    if namespace:
        memories = _validate_namespace_results(
            memories,
            namespace,
            operation="memory list",
        )
    if limit == 0:
        return memories
    return memories[:limit]


def delete_memory(memory_id: str) -> bool:
    """Delete a specific memory by ID.

    Raises MemoryError on unexpected backend failures.
    """
    mem = _get_memory()
    try:
        existing = mem.get(memory_id)
    except Exception as exc:
        raise _memory_failure(
            "memory delete",
            exc,
            memory_id=memory_id,
            phase="lookup",
        ) from exc
    if existing is None:
        return False
    if not isinstance(existing, dict):
        raise MemoryError(
            "memory delete failed: lookup returned "
            f"{type(existing).__name__}, expected dict or None",
            details={
                "operation": "memory delete",
                "memory_id": memory_id,
                "phase": "lookup",
                "response_type": type(existing).__name__,
            },
        )
    if existing.get("id") != memory_id:
        raise MemoryError(
            "memory delete failed: lookup returned a mismatched memory id",
            details={
                "operation": "memory delete",
                "memory_id": memory_id,
                "phase": "lookup",
            },
        )

    try:
        result = mem.delete(memory_id=memory_id)
    except Exception as exc:
        raise _memory_failure(
            "memory delete",
            exc,
            memory_id=memory_id,
        ) from exc
    message = result.get("message") if isinstance(result, dict) else None
    if not isinstance(message, str) or "deleted successfully" not in message.lower():
        raise MemoryError(
            "memory delete failed: backend did not confirm deletion",
            details={
                "operation": "memory delete",
                "memory_id": memory_id,
                "phase": "delete",
                "response_type": type(result).__name__,
            },
        )
    logger.info("Memory deleted: %s", memory_id)
    return True


def consolidate_session(session_id: str, messages: list[dict]) -> bool:
    """Extract key facts from a closed session and persist to long-term memory.

    Reads user messages from the session, creates a summary, and stores
    it via add_memory(). Returns True if facts were stored and False when the
    session has no user content. Raises MemoryError on persistence failure.
    """
    if not messages:
        logger.info(
            "Session %s closed with no messages — nothing to consolidate",
            session_id or "<anonymous>",
        )
        return False

    user_msgs = [
        m.get("content", "") for m in messages if m.get("role") == "user" and m.get("content")
    ]
    if not user_msgs:
        logger.info(
            "Session %s closed with no user messages — nothing to consolidate",
            session_id or "<anonymous>",
        )
        return False

    # Build a concise session summary from user messages
    joined = "\n".join(f"- {msg[:120]}" for msg in user_msgs[-20:])
    session_summary = f"[session {session_id or 'anonymous'}] Key topics discussed:\n{joined}"

    try:
        stored = add_memory(
            session_summary,
            namespace="sessions",
            metadata={
                "session_id": session_id or "anonymous",
                "message_count": len(messages),
                "user_message_count": len(user_msgs),
            },
        )
        if not stored:
            logger.info(
                "Session %s produced no new long-term memory changes",
                session_id or "<anonymous>",
            )
            return False
        logger.info(
            "Session %s consolidated: %d user messages stored",
            session_id or "<anonymous>",
            len(user_msgs),
        )
        return True
    except Exception as exc:
        raise _memory_failure(
            "session consolidation",
            exc,
            session_id=session_id or "anonymous",
        ) from exc
