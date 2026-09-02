"""Resolve durable object references embedded invisibly in chat messages.

The composer persists stable refs as HTML comments so retries/reloads keep the
same identity while the visible user message stays readable. This module is a
read-only projection: ProjectStore, ArtifactStore, and chats_store remain the
owners of the referenced objects.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from gateway import artifact_store, chat_lifecycle, chats_store, project_store

_CONTEXT_RE = re.compile(
    r"(?m)^\s*<!--\s*kitty-context:(project|artifact|chat):([^\s>]+)\s*-->\s*$"
)
_ALLOWED_KINDS = frozenset({"project", "artifact", "chat"})
_MAX_REFS = 8
_MAX_ARTIFACT_CHARS = 8_000
_MAX_CHAT_MESSAGES = 8
_MAX_CHAT_CHARS = 6_000


@dataclass(frozen=True)
class ContextReference:
    kind: str
    ref_id: str


def extract_context_references(text: str) -> tuple[str, list[ContextReference]]:
    refs: list[ContextReference] = []
    seen: set[tuple[str, str]] = set()
    for match in _CONTEXT_RE.finditer(text):
        kind = match.group(1)
        ref_id = match.group(2).strip()
        key = (kind, ref_id)
        if kind in _ALLOWED_KINDS and ref_id and key not in seen and len(refs) < _MAX_REFS:
            refs.append(ContextReference(kind=kind, ref_id=ref_id))
            seen.add(key)
    if not refs:
        return text, []
    clean = _CONTEXT_RE.sub("", text).strip()
    clean = re.sub(r"\n{3,}", "\n\n", clean)
    return clean, refs


def strip_context_markers(text: str) -> str:
    return extract_context_references(text)[0]


def resolve_context_references(
    refs: list[ContextReference],
) -> tuple[str, list[str]]:
    blocks: list[str] = []
    warnings: list[str] = []
    for ref in refs[:_MAX_REFS]:
        try:
            if ref.kind == "project":
                blocks.append(_project_block(ref.ref_id))
            elif ref.kind == "artifact":
                blocks.append(_artifact_block(ref.ref_id))
            elif ref.kind == "chat":
                blocks.append(_chat_block(ref.ref_id))
            else:
                warnings.append(f"unsupported context kind: {ref.kind}")
        except Exception as exc:
            warnings.append(f"{ref.kind}:{ref.ref_id}: {type(exc).__name__}: {exc}")
    useful = [block for block in blocks if block]
    if not useful:
        return "", warnings
    return "## Explicit context\nUse these user-selected Kitty objects as primary context for this turn.\n\n" + "\n\n".join(useful), warnings


def _project_block(ref_id: str) -> str:
    try:
        project_id = int(ref_id)
    except ValueError as exc:
        raise ValueError("project id must be an integer") from exc
    project = project_store.get(project_id)
    if project is None:
        raise LookupError("project not found")
    lines = [
        f"### Project: {project.get('name') or project_id}",
        f"Kind: {project.get('kind') or 'unknown'}",
        f"Status: {project.get('status') or 'unknown'}",
    ]
    if project.get("summary"):
        lines.append(f"Summary: {project['summary']}")
    actions = project.get("next_actions") or []
    if actions:
        lines.append("Next actions: " + "; ".join(str(item) for item in actions[:5]))
    questions = project.get("open_questions") or []
    if questions:
        lines.append("Open questions: " + "; ".join(str(item) for item in questions[:5]))
    return "\n".join(lines)


def _artifact_block(ref_id: str) -> str:
    artifact = artifact_store.get_artifact(ref_id)
    if artifact is None:
        raise LookupError("artifact not found")
    name = artifact.get("display_name") or ref_id
    media_type = str(artifact.get("media_type") or "application/octet-stream").lower()
    state = artifact.get("state") or "unknown"
    lines = [f"### Artifact: {name}", f"Type: {media_type}", f"State: {state}"]
    if state == "ready" and media_type in {"text/plain", "text/markdown", "text/x-markdown"}:
        storage_uri = artifact.get("storage_uri")
        if not isinstance(storage_uri, str) or not storage_uri:
            raise LookupError("artifact has no readable content")
        path = Path(storage_uri)
        if not path.is_file():
            raise LookupError("artifact backing file is missing")
        current_hash, current_size = artifact_store._hash_file(path)
        if current_hash != str(artifact.get("content_hash") or "") or current_size != artifact.get("size_bytes"):
            raise ValueError("artifact changed on disk; refresh or re-import it before referencing it")
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError("artifact content is not valid UTF-8 text") from exc
        text = text[:_MAX_ARTIFACT_CHARS]
        if text:
            lines.extend(["Content:", text])
    return "\n".join(lines)


def _lifecycle_chat_messages(ref_id: str) -> list[dict] | None:
    """Turns from the durable lifecycle ledger, or None when unavailable.

    The chats blob is a cache that can miss turns recovered into the lifecycle
    ledger, so referenced conversations read from the ledger first.
    """
    try:
        snapshot = chat_lifecycle.list_conversation(ref_id)
    except Exception:
        return None
    messages: list[dict] = []
    for turn in snapshot.get("turns") or []:
        for message in turn.get("messages") or []:
            if not isinstance(message, dict) or message.get("status") == "interrupted":
                continue
            role = str(message.get("role") or "")
            content = message.get("content")
            if role in {"user", "assistant"} and isinstance(content, str) and content.strip():
                messages.append({"role": role, "content": content})
    return messages or None


def _chat_block(ref_id: str) -> str:
    chat = chats_store.get_chat(ref_id)
    ledger_messages = _lifecycle_chat_messages(ref_id)
    if chat is None and ledger_messages is None:
        raise LookupError("conversation not found")
    title = (chat or {}).get("title") or "Untitled conversation"
    lines = [f"### Conversation: {title}"]
    objective = (chat or {}).get("objective")
    if objective:
        lines.append(f"Objective: {objective}")
    used = 0
    history = ledger_messages if ledger_messages is not None else ((chat or {}).get("messages") or [])
    for message in history[-_MAX_CHAT_MESSAGES:]:
        if not isinstance(message, dict):
            continue
        role = str(message.get("role") or "unknown")
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            continue
        content = strip_context_markers(content).strip()
        if not content:
            continue
        remaining = _MAX_CHAT_CHARS - used
        if remaining <= 0:
            break
        content = content[:remaining]
        lines.append(f"{role}: {content}")
        used += len(content)
    return "\n".join(lines)
