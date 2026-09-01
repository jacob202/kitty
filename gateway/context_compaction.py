"""Context Compaction — auto-summarize long chat threads into memory checkpoints.

When a conversation exceeds MESSAGE_THRESHOLD messages, the compaction system
replaces the older messages with a single "Previously..." summary and persists
a memory checkpoint via explicit_memory so the thread stays bounded while
preserving narrative continuity.
"""

from __future__ import annotations

import logging
import uuid

from gateway import chat_lifecycle, chats_store, explicit_memory, llm_client

logger = logging.getLogger("kitty.context_compaction")

# Threshold: when a conversation has more than this many messages, trigger
# compaction on the next read/write cycle (excluding the last N kept intact).
MESSAGE_THRESHOLD = 20
KEEP_LAST = 10


def _build_summary_prompt(messages: list[dict]) -> list[dict]:
    """Build the LLM prompt for summarising a block of conversation messages.

    Returns a two-turn message list (system instruction + user content dump).
    """
    system_prompt = (
        "You are a conversation summariser. Condense the following chat messages "
        "into a single concise paragraph that captures:
"
        "- The topic or question the user started with
"
        "- Key facts, decisions, or answers reached
"
        "- Any follow-up actions or open questions

"
        "Write it as a first-person narrative summary starting with "
        '"Previously..." so it reads naturally when inserted as the first '
        "message of a continued conversation."
    )

    lines: list[str] = []
    for msg in messages:
        role = msg.get("role", "unknown")
        content = str(msg.get("content", "") or "")
        if not content.strip():
            continue
        lines.append(f"[{role}]: {content}")

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "

".join(lines) if lines else "(empty conversation)"},
    ]


def compact_chat(chat_id: str) -> dict | None:
    """Run context compaction for a chat, returning checkpoint metadata.

    1. Fetch the chat and its lifecycle turns
    2. Count total messages — skip if below threshold
    3. Build the summary prompt from all but the last KEEP_LAST messages
    4. Call the LLM for the summary
    5. Store the summary as an explicit memory checkpoint
    6. Update the chat blob: replace compacted messages with the summary
    7. Return checkpoint info (or None if compaction was not needed)
    """
    chat = chats_store.get_chat(chat_id)
    if chat is None:
        logger.warning("compact_chat: chat %s not found", chat_id)
        return None

    # Get the full message list from the lifecycle ledger
    try:
        state = chat_lifecycle.list_conversation(chat_id)
    except chat_lifecycle.ChatLifecycleError:
        logger.warning("compact_chat: lifecycle for %s not available", chat_id)
        return None

    turns = state.get("turns") or []
    messages: list[dict] = []
    for turn in turns:
        for msg in turn.get("messages") or []:
            messages.append({
                "id": msg.get("id"),
                "role": msg.get("role"),
                "content": msg.get("content"),
                "created_at": msg.get("created_at"),
            })

    if len(messages) <= MESSAGE_THRESHOLD:
        logger.info(
            "compact_chat: %s has %d messages, threshold is %d — skipping",
            chat_id, len(messages), MESSAGE_THRESHOLD,
        )
        return None

    # Split: compact everything except the last KEEP_LAST messages
    compactable = messages[:-KEEP_LAST] if KEEP_LAST < len(messages) else messages[:0]
    keep = messages[-KEEP_LAST:] if len(messages) >= KEEP_LAST else messages

    if not compactable:
        logger.info("compact_chat: %s has no compactable messages", chat_id)
        return None

    # Build and call the LLM
    llm_messages = _build_summary_prompt(compactable)
    try:
        summary = llm_client.call_llm(
            llm_messages,
            model="kitty-small",
            max_tokens=500,
            temperature=0.3,
            operation="context_compaction.summarise",
        )
    except Exception as exc:
        logger.exception("compact_chat: LLM summarisation failed for %s: %s", chat_id, exc)
        return None

    if not summary or not summary.strip():
        logger.warning("compact_chat: LLM returned empty summary for %s", chat_id)
        return None

    summary = summary.strip()

    # Store as an explicit memory checkpoint
    checkpoint_id = f"chk_{uuid.uuid4().hex[:16]}"
    try:
        memory_record = explicit_memory.remember(
            text=f"[checkpoint:{checkpoint_id}] Conversation checkpoint for {chat_id}: {summary}",
            namespace="facts",
            memory_key=f"chat_checkpoint_{chat_id}",
            source_kind="system",
            source_ref=f"chat:{chat_id}",
            pinned=False,
        )
        memory_id = memory_record.get("id", "unknown")
    except Exception as exc:
        logger.exception("compact_chat: failed to store memory checkpoint for %s: %s", chat_id, exc)
        memory_id = "stored_without_id"

    # Update the chat's message list in the chat blob
    summary_message = {
        "role": "assistant",
        "content": f"Previously... {summary}",
        "compacted": True,
        "checkpoint_id": checkpoint_id,
        "memory_id": memory_id,
    }

    # Reconstruct the full chat message list from the blob's existing messages
    chat_messages: list[dict] = chat.get("messages") or []
    if chat_messages:
        # Replace the compacted block with the summary
        trimmed = chat_messages[:-KEEP_LAST] if len(chat_messages) > KEEP_LAST else []
        trimmed.append(summary_message)
        # Append the kept tail
        kept = chat_messages[-KEEP_LAST:] if len(chat_messages) >= KEEP_LAST else []
        chat_messages = trimmed + kept
    else:
        # Fallback: build from lifecycle messages
        kept_msgs = []
        for msg in keep:
            kept_msgs.append({
                "id": msg.get("id"),
                "role": msg.get("role"),
                "content": msg.get("content"),
                "created_at": msg.get("created_at"),
            })
        chat_messages = [summary_message] + kept_msgs

    chat["messages"] = chat_messages
    chat["compacted"] = True
    chat["last_checkpoint_id"] = checkpoint_id

    # Persist the updated chat blob
    try:
        chats_store.upsert_chat(chat)
    except Exception as exc:
        logger.exception("compact_chat: failed to persist updated chat %s: %s", chat_id, exc)
        return None

    result = {
        "chat_id": chat_id,
        "checkpoint_id": checkpoint_id,
        "memory_id": memory_id,
        "compacted_count": len(compactable),
        "kept_count": len(keep),
        "summary": summary,
    }
    logger.info(
        "compact_chat: %s compacted %d messages into checkpoint %s (memory %s)",
        chat_id, len(compactable), checkpoint_id, memory_id,
    )
    return result


def auto_compact_chat(chat_id: str) -> dict | None:
    """Auto-trigger compaction for a chat if it exceeds the threshold.

    Designed to be called after each new message is added, so the UI or
    chat-backend can check whether compaction is due without a separate
    API call. Returns the same result shape as compact_chat, or None
    if no compaction was needed.
    """
    chat = chats_store.get_chat(chat_id)
    if chat is None:
        return None

    # Skip if already compacted (avoid re-summarising on every message)
    if chat.get("compacted"):
        return None

    # Check message count from lifecycle
    try:
        state = chat_lifecycle.list_conversation(chat_id)
    except chat_lifecycle.ChatLifecycleError:
        return None

    turns = state.get("turns") or []
    message_count = sum(len(turn.get("messages") or []) for turn in turns)

    if message_count <= MESSAGE_THRESHOLD:
        return None

    logger.info("auto_compact_chat: %s has %d messages, triggering compaction", chat_id, message_count)
    return compact_chat(chat_id)
