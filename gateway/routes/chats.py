"""Kitty-chat session persistence — backed by kitty.db via chats_store.

Phase C C3: the route reads and writes through chats_store instead of
data/kitty/chats.json. The wire contract (paths, request/response
shapes) is unchanged.
"""
from __future__ import annotations

import base64
import json
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request

from gateway import artifact_store, chat_lifecycle, chats_store

logger = logging.getLogger("kitty.routes.chats")

router = APIRouter(tags=["chats"])

# LIBRARY-CHAT-001: images that can be attached from Library into a chat
# message. The chat-completions path turns each into an OpenAI image_url part,
# so only raster image types the model can actually read are allowed.
CHAT_IMAGE_MIME_TYPES = {"image/png", "image/jpeg", "image/webp"}
CHAT_IMAGE_MAX_BYTES = 5 * 1024 * 1024  # 5 MiB


def _recover_memory_items(raw_memory: object) -> list[dict[str, str]]:
    """Normalize legacy strings and current records from durable ledger JSON."""
    try:
        decoded = json.loads(raw_memory) if isinstance(raw_memory, str) else []
    except json.JSONDecodeError:
        return []
    if not isinstance(decoded, list):
        return []

    normalized: list[dict[str, str]] = []
    for item in decoded:
        if isinstance(item, str) and item:
            normalized.append({"text": item})
            continue
        if not isinstance(item, dict) or set(item) - {"text", "memory_id"}:
            return []
        text = item.get("text")
        if not isinstance(text, str) or not text:
            return []
        record = {"text": text}
        memory_id = item.get("memory_id")
        if memory_id is not None:
            if not isinstance(memory_id, str) or not memory_id:
                return []
            record["memory_id"] = memory_id
        normalized.append(record)
    return normalized


@router.get("/chats")
async def get_chats():
    """Return all saved chat sessions."""
    return {"chats": chats_store.list_chats()}


@router.post("/chats")
async def upsert_chat(request: Request):
    """Create or update a chat session by id."""
    chat = await request.json()
    if not chat.get("id"):
        raise HTTPException(status_code=400, detail="id required")
    chats_store.upsert_chat(chat)
    return {"ok": True}


@router.delete("/chats/{chat_id}")
async def delete_chat(chat_id: str):
    """Delete a chat session."""
    chats_store.delete_chat(chat_id)
    return {"ok": True}


@router.patch("/chats/{chat_id}/objective")
async def patch_chat_objective(chat_id: str, request: Request):
    """Set or clear a chat's per-thread objective."""
    try:
        body = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise HTTPException(status_code=400, detail=f"invalid JSON body: {exc}") from exc
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="request body must be an object")
    if "objective" not in body:
        raise HTTPException(status_code=400, detail="objective field required")
    objective = body["objective"]
    if objective is not None:
        if not isinstance(objective, str):
            raise HTTPException(
                status_code=400,
                detail="objective must be a string or null",
            )
        if len(objective) > 500:
            raise HTTPException(
                status_code=400,
                detail=f"objective must be at most 500 characters, got {len(objective)}",
            )
    try:
        updated = chats_store.patch_objective(chat_id, objective)
    except chats_store.ChatNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return updated


@router.get("/chats/{chat_id}/lifecycle")
def get_chat_lifecycle(chat_id: str) -> dict:
    try:
        return chat_lifecycle.list_conversation(chat_id)
    except chat_lifecycle.ChatLifecycleError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def _recover_messages(conversation_id: str) -> list[dict]:
    """Rebuild an ordered UI message list from the durable lifecycle ledger.

    Falls back gracefully: a missing conversation (no ledger entry yet) yields
    an empty list so the caller can keep using the legacy chat blob.

    Deduplication: when the same user message is retried (same
    source_message_id across turns), only the most recent turn's messages are
    retained so restarts never show duplicated user text.

    Artifact metadata is collected first and loaded with one batched store
    lookup instead of opening a database connection for every attachment.
    """
    try:
        state = chat_lifecycle.list_conversation(conversation_id)
    except chat_lifecycle.ChatLifecycleError:
        return []

    messages: list[dict] = []
    seen_source_ids: set[str] = set()
    artifact_ids_needed: set[str] = set()
    turns = [turn for turn in state.get("turns", []) if turn is not None]
    latest_turn_for_source: dict[str, str] = {}
    for turn in turns:
        for msg in turn.get("messages", []):
            source_id = msg.get("source_message_id")
            if source_id is not None and msg.get("role") == "user":
                latest_turn_for_source[source_id] = turn["id"]

    # A retry reuses the original user message's source_message_id but is not
    # guaranteed to resend its attachments, and the superseded turn carrying
    # them is dropped below. Collect every attachment ever recorded against a
    # source_message_id up front so a retried message still shows the
    # attachments the user originally sent.
    attachments_by_source: dict[str, list[str]] = {}
    for turn in turns:
        for msg in turn.get("messages", []):
            if msg.get("role") != "user":
                continue
            source_id = msg.get("source_message_id")
            if source_id is None:
                continue
            raw_artifacts = msg.get("artifact_ids") or "[]"
            try:
                ids = json.loads(raw_artifacts) if isinstance(raw_artifacts, str) else raw_artifacts
            except (TypeError, json.JSONDecodeError):
                continue
            if not isinstance(ids, list):
                continue
            merged = attachments_by_source.setdefault(source_id, [])
            for art_id in ids:
                if isinstance(art_id, str) and art_id and art_id not in merged:
                    merged.append(art_id)

    for turn in turns:
        user_source_ids = [
            msg.get("source_message_id")
            for msg in turn.get("messages", [])
            if msg.get("role") == "user" and msg.get("source_message_id") is not None
        ]
        if user_source_ids and any(
            latest_turn_for_source.get(source_id) != turn["id"]
            for source_id in user_source_ids
        ):
            continue
        attempt_model = None
        for attempt in turn.get("attempts", []):
            if attempt.get("resolved_model"):
                attempt_model = attempt["resolved_model"]
                break
        turn_status = turn.get("status")
        for msg in turn.get("messages", []):
            source_id = msg.get("source_message_id")
            if source_id is not None and msg["role"] == "user":
                if source_id in seen_source_ids:
                    continue
                seen_source_ids.add(source_id)

            if source_id is not None and msg["role"] == "user" and source_id in attachments_by_source:
                artifact_ids = attachments_by_source[source_id]
            else:
                raw_artifacts = msg.get("artifact_ids") or "[]"
                try:
                    artifact_ids = (
                        json.loads(raw_artifacts)
                        if isinstance(raw_artifacts, str)
                        else raw_artifacts
                    )
                except (TypeError, json.JSONDecodeError):
                    artifact_ids = []
                if not isinstance(artifact_ids, list):
                    artifact_ids = []
            artifact_ids_needed.update(
                art_id for art_id in artifact_ids if isinstance(art_id, str) and art_id
            )

            messages.append(
                {
                    "id": msg["id"],
                    "role": msg["role"],
                    "content": msg["content"],
                    "created_at": msg["created_at"],
                    "model": attempt_model if msg["role"] == "assistant" else None,
                    "status": turn_status,
                    "artifact_ids": artifact_ids,
                    "memory_items": _recover_memory_items(msg.get("memory_items")),
                }
            )

    artifacts_by_id = artifact_store.get_artifacts(list(artifact_ids_needed))

    recovered: list[dict] = []
    for message in messages:
        attachments = []
        for art_id in message.pop("artifact_ids", []):
            artifact = artifacts_by_id.get(art_id)
            if artifact is None:
                continue
            attachments.append(
                {
                    "id": artifact["id"],
                    "display_name": artifact["display_name"],
                    "media_type": artifact["media_type"],
                    "size": artifact["size_bytes"],
                }
            )
        message["attachments"] = attachments
        recovered.append(message)

    return recovered


def _resolve_chat_image_attachment(artifact_id: str, *, include_data_url: bool = True) -> dict:
    """Resolve a stored artifact to a chat-ready image attachment.

    Raises a plain-language HTTPException for any artifact that cannot be used
    in chat: unknown id, not an image, unsupported image type, not ready, or
    over the 5 MiB pilot limit. The caller decides whether the artifact also
    needs to exist as a registered attachment before dispatch.
    """
    artifact = artifact_store.get_artifact(artifact_id)
    if artifact is None:
        raise HTTPException(status_code=404, detail="That saved file no longer exists.")
    if artifact.get("state") != "ready":
        raise HTTPException(
            status_code=409,
            detail="That saved file is not ready to use in chat yet.",
        )
    media_type = artifact.get("media_type") or "application/octet-stream"
    if not media_type.startswith("image/"):
        raise HTTPException(
            status_code=415,
            detail="Only images can be attached into a chat message from Library.",
        )
    if media_type not in CHAT_IMAGE_MIME_TYPES:
        raise HTTPException(
            status_code=415,
            detail="That image type isn't supported in chat yet — use PNG, JPEG, or WebP.",
        )
    size_bytes = artifact.get("size_bytes")
    if not isinstance(size_bytes, int) or size_bytes <= 0:
        raise HTTPException(status_code=409, detail="That saved file has no readable size.")
    if size_bytes > CHAT_IMAGE_MAX_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"That image is {_format_bytes(size_bytes)} — chat attachments are limited to 5 MB.",
        )
    storage_uri = artifact.get("storage_uri")
    if not storage_uri:
        raise HTTPException(status_code=409, detail="That saved file has no readable content.")
    path = Path(storage_uri)
    if not path.is_file():
        raise HTTPException(status_code=409, detail="That saved file is missing from disk.")
    try:
        actual_size = path.stat().st_size
    except OSError as exc:
        logger.warning("could not stat artifact %s for chat: %s", artifact_id, exc)
        raise HTTPException(
            status_code=409, detail="That saved file could not be read right now."
        ) from exc
    if actual_size <= 0:
        raise HTTPException(status_code=409, detail="That saved file has no readable size.")
    if actual_size > CHAT_IMAGE_MAX_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"That image is {_format_bytes(actual_size)} — chat attachments are limited to 5 MB.",
        )
    attachment = {
        "id": artifact["id"],
        "display_name": artifact.get("display_name") or path.name,
        "media_type": media_type,
        "size": actual_size,
    }
    if not include_data_url:
        return attachment
    try:
        with path.open("rb") as handle:
            content = handle.read(CHAT_IMAGE_MAX_BYTES + 1)
    except OSError as exc:
        logger.warning("could not read artifact %s for chat: %s", artifact_id, exc)
        raise HTTPException(
            status_code=409, detail="That saved file could not be read right now."
        ) from exc
    if len(content) > CHAT_IMAGE_MAX_BYTES:
        raise HTTPException(
            status_code=413,
            detail="That image grew beyond the 5 MB chat attachment limit.",
        )
    encoded = base64.b64encode(content).decode("ascii")
    return {**attachment, "data_url": f"data:{media_type};base64,{encoded}"}


def _format_bytes(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size / (1024 * 1024):.1f} MB"


@router.post("/chats/use-in-chat")
async def use_in_chat(request: Request) -> dict:
    """Resolve a saved artifact into a chat-ready image attachment.

    This is the Library → Chat bridge for LIBRARY-CHAT-001. It validates type
    and size before any network dispatch and returns only the attachment
    metadata the composer renders. The durable artifact id is resolved to image
    bytes later, inside the trusted completions route, so the model receives the
    image exactly once. Errors are plain language with no internal paths, ids,
    or status codes.
    """
    try:
        body = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise HTTPException(status_code=400, detail="invalid JSON body") from exc
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="request body must be an object")
    artifact_id = body.get("artifact_id")
    if not isinstance(artifact_id, str) or not artifact_id.strip():
        raise HTTPException(status_code=400, detail="artifact_id is required")
    return _resolve_chat_image_attachment(artifact_id.strip(), include_data_url=False)


@router.get("/chats/{chat_id}/messages")
def get_chat_messages(chat_id: str) -> dict:
    """Recover ordered chat history from the normalized lifecycle ledger.

    The legacy chat blob stays the compatibility record; this endpoint is the
    honest durable read surface for restart/recovery when the in-memory UI state
    is gone but the ledger survived.
    """
    return {"conversation_id": chat_id, "messages": _recover_messages(chat_id)}
