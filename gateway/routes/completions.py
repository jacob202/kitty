"""LiteLLM chat-completions proxy and session close."""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field

from gateway import chat_lifecycle, chats_store, context_references
from gateway.chat_errors import (
    FRIENDLY_MESSAGES,
    ChatErrorKind,
    ChatTurnError,
    sse_error_event,
)
from gateway.constants import MAX_BODY_BYTES
from gateway.domain_router import classify_domain
from gateway.http_client import get_http_client
from gateway.llm_client import (
    chat_completions_non_stream,
    iter_chat_completions_stream,
    log_chat_trace,
    selected_provider_name,
)
from gateway.memory_graph import MemoryEvidence
from gateway.model_routing import resolve_chat_route
from gateway.paths import LITELLM_BASE, LITELLM_KEY, LOG_FILE
from gateway.runtime_manifest import compact_runtime_context, compose_manifest

logger = logging.getLogger("kitty.gateway")
router = APIRouter(tags=["completions"])

_NO_TOOL_EXECUTOR_SYSTEM = """
This chat runtime does not currently have a tool executor. Do not emit XML, DSML,
or tool-call syntax as ordinary assistant text. Do not claim that a command, search,
file operation, or external action ran unless an execution result is present in the
conversation. When execution is required, state plainly that tools are unavailable
in this chat runtime.
""".strip()


def _strip_context_markers_from_content(content):
    if isinstance(content, str):
        return context_references.strip_context_markers(content)
    if isinstance(content, list):
        cleaned = []
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text" and isinstance(part.get("text"), str):
                cleaned.append({**part, "text": context_references.strip_context_markers(part["text"])})
            else:
                cleaned.append(part)
        return cleaned
    return content


def _prepare_explicit_context(messages: list[dict]):
    """Strip persisted markers from model-visible history and resolve latest refs."""
    latest_user_index = None
    raw_user_text = ""
    for index in range(len(messages) - 1, -1, -1):
        if messages[index].get("role") == "user":
            latest_user_index = index
            raw_user_text = _message_text(messages[index].get("content", ""))
            break

    clean_messages = [
        {**message, "content": _strip_context_markers_from_content(message.get("content", ""))}
        for message in messages
    ]
    if latest_user_index is None:
        return clean_messages, "", "", "", []

    clean_user_text, refs = context_references.extract_context_references(raw_user_text)
    context_block, warnings = context_references.resolve_context_references(refs)
    return clean_messages, clean_user_text, raw_user_text, context_block, warnings


def _message_budget_units(message: dict) -> int:
    return len(
        json.dumps(message, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    )


def _prefix_for_system_budget(parts: dict[str, str], name: str, text: str, budget: int) -> str:
    """Largest codepoint-safe prefix that keeps the serialized system message in budget."""
    order = ("bundle", "runtime", "tool")

    def rendered(candidate: str) -> str:
        trial = dict(parts)
        if candidate:
            trial[name] = candidate
        return "\n\n".join(trial[key] for key in order if trial.get(key))

    if _message_budget_units({"role": "system", "content": rendered(text)}) <= budget:
        return text
    low, high = 0, len(text)
    while low < high:
        mid = (low + high + 1) // 2
        candidate = text[:mid]
        if _message_budget_units({"role": "system", "content": rendered(candidate)}) <= budget:
            low = mid
        else:
            high = mid - 1
    return text[:low]


def _atomic_history_groups(messages: list[dict]) -> list[list[dict]]:
    """Group assistant tool calls with their contiguous tool results."""
    groups: list[list[dict]] = []
    index = 0
    while index < len(messages):
        message = messages[index]
        if message.get("role") == "assistant" and message.get("tool_calls"):
            group = [message]
            index += 1
            while index < len(messages) and messages[index].get("role") == "tool":
                group.append(messages[index])
                index += 1
            groups.append(group)
            continue
        groups.append([message])
        index += 1
    return groups


def _fit_final_model_messages(
    *,
    bundle_system: str,
    runtime_system: str,
    tool_system: str,
    messages: list[dict],
    token_cap: int,
) -> tuple[list[dict], list[str]]:
    """Bound the payload while preserving the current turn and tool exchanges."""
    non_system = [dict(message) for message in messages if message.get("role") != "system"]
    current_index = next(
        (index for index in range(len(non_system) - 1, -1, -1) if non_system[index].get("role") == "user"),
        None,
    )
    if current_index is None:
        raise HTTPException(status_code=400, detail="chat request requires a user message")
    current_turn = non_system[current_index:]
    current_units = sum(_message_budget_units(message) for message in current_turn)
    if current_units > token_cap:
        raise HTTPException(status_code=413, detail="Current turn exceeds the model context budget")

    warnings: list[str] = []
    system_budget = token_cap - current_units
    selected: dict[str, str] = {}
    # Safety/tool truth first, then runtime truth, then contextual enrichment.
    for name, part, required in (
        ("tool", tool_system, bool(tool_system)),
        ("runtime", runtime_system, bool(runtime_system)),
        ("bundle", bundle_system, False),
    ):
        if not part:
            continue
        fitted = _prefix_for_system_budget(selected, name, part, system_budget)
        if required and fitted != part:
            required_context = "runtime context" if name == "runtime" else "safety context"
            raise HTTPException(
                status_code=413,
                detail=f"Current message leaves no room for required chat {required_context}",
            )
        if fitted:
            selected[name] = fitted
        if fitted != part:
            warnings.append(f"context_budget:final_system:{name}: clipped")

    system_content = "\n\n".join(
        selected[key] for key in ("bundle", "runtime", "tool") if selected.get(key)
    )
    final: list[dict] = []
    used = current_units
    if system_content:
        system_message = {"role": "system", "content": system_content}
        used += _message_budget_units(system_message)
        final.append(system_message)

    history_groups: list[list[dict]] = []
    dropped = 0
    for group in reversed(_atomic_history_groups(non_system[:current_index])):
        units = sum(_message_budget_units(message) for message in group)
        if used + units <= token_cap:
            history_groups.append(group)
            used += units
        else:
            dropped += len(group)
    if dropped:
        warnings.append(f"context_budget:history: dropped {dropped} older message(s)")
    for group in reversed(history_groups):
        final.extend(group)
    final.extend(current_turn)

    total = sum(_message_budget_units(message) for message in final)
    if total > token_cap:
        raise RuntimeError(f"final model-visible payload exceeded context cap: {total}>{token_cap}")
    return final, warnings

def route_model(message: str) -> str:
    """Compatibility routing seam for tests and callers that still patch this Module."""
    return resolve_chat_route("kitty-default", message, reroute_virtual_models=True).model


def _has_image(content: object) -> bool:
    """Whether a message carries an image part."""
    return isinstance(content, list) and any(
        isinstance(part, dict) and part.get("type") == "image_url" for part in content
    )


def _message_text(content: object) -> str:
    """The text of a message, whether or not it also carries images.

    An OpenAI message with an attachment sends ``content`` as a list of parts,
    not a string. Everything downstream — complexity, domain, memory, the
    repairs-intent check — assumed a string, so uploading any image to the chat
    endpoint raised ``'list' object has no attribute 'strip'`` and returned 500.
    """
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    return "\n".join(
        part["text"]
        for part in content
        if isinstance(part, dict)
        and part.get("type") == "text"
        and isinstance(part.get("text"), str)
    )


def _attach_images_to_user_message(
    messages: list[dict],
    image_parts: list[dict],
) -> list[dict]:
    """Attach resolved image parts to the latest user message.

    The chat route receives ``attachment_ids`` (durable artifact ids) and the
    wire messages only carry text. This splices the resolved image parts into
    the current user message so the model actually sees the image. The user
    text stays a text part so every existing text consumer keeps working.
    """
    if not image_parts:
        return messages
    updated = list(messages)
    for index in range(len(updated) - 1, -1, -1):
        message = updated[index]
        if message.get("role") != "user":
            continue
        content = message.get("content", "")
        if isinstance(content, str):
            parts = [{"type": "text", "text": content}] if content else []
        elif isinstance(content, list):
            parts = list(content)
        else:
            parts = []
        parts.extend(image_parts)
        updated[index] = {**message, "content": parts}
        return updated
    return updated


def _resolve_attachment_image_parts(attachment_ids: list[str]) -> list[dict]:
    """Turn durable artifact ids into OpenAI image_url parts.

    Reuses the same type/size/state validation as the Library → chat bridge
    (``gateway/routes/chats.py``) so a Library-staged image and a direct
    ``attachment_ids`` send agree on what is attachable. Any failure raises a
    plain-language HTTPException before the request is dispatched upstream.
    """
    from gateway.routes.chats import _resolve_chat_image_attachment

    parts: list[dict] = []
    for artifact_id in attachment_ids:
        attachment = _resolve_chat_image_attachment(artifact_id)
        data_url = attachment.get("data_url")
        if not isinstance(data_url, str) or not data_url:
            raise HTTPException(
                status_code=409,
                detail="That saved file could not be prepared for chat.",
            )
        parts.append({"type": "image_url", "image_url": {"url": data_url}})
    return parts


_ATTACHMENT_FAILURE_MESSAGE = (
    "Kitty couldn't use that image. Remove it and stage the image again."
)


class CloseSessionRequest(BaseModel):
    messages: list[dict] = Field(default_factory=list)
    session_id: str = ""


def _finish_lifecycle_or_raise(
    handle: chat_lifecycle.TurnHandle,
    *,
    status: str,
    assistant_text: str,
    resolved_model: str | None = None,
    error: str | None = None,
    memory_items: list[MemoryEvidence] | None = None,
) -> None:
    try:
        chat_lifecycle.finish_turn(
            handle,
            status=status,
            assistant_text=assistant_text,
            resolved_model=resolved_model,
            error=error,
            memory_items=memory_items,
        )
    except Exception as exc:
        raise RuntimeError(
            f"chat lifecycle finalization failed for turn {handle.turn_id}: {exc}"
        ) from exc


def _assistant_text_from_result(result: dict) -> str:
    choices = result.get("choices")
    if not isinstance(choices, list) or not choices:
        raise RuntimeError("non-stream chat response omitted choices")
    message = choices[0].get("message")
    if not isinstance(message, dict):
        raise RuntimeError("non-stream chat response omitted assistant message")
    content = message.get("content", "")
    if not isinstance(content, str):
        raise RuntimeError("non-stream chat response content was not text")
    return content


@router.post("/v1/chat/completions")
async def chat_completions(request: Request):
    from gateway.buddy import (
        on_context_fetch,
        on_request_error,
        on_request_start,
        on_request_success,
    )

    content_length = request.headers.get("content-length")
    if content_length:
        try:
            declared_length = int(content_length)
        except ValueError:
            on_request_error()
            return Response(status_code=400, content="Invalid Content-Length header")
        if declared_length < 0:
            on_request_error()
            return Response(status_code=400, content="Invalid Content-Length header")
        if declared_length > MAX_BODY_BYTES:
            on_request_error()
            return Response(status_code=413, content="Request body too large")

    on_request_start()

    body = await request.json()
    raw_project_id = body.get("project_id")
    if raw_project_id is not None and (
        isinstance(raw_project_id, bool)
        or not isinstance(raw_project_id, int)
        or raw_project_id <= 0
    ):
        raise HTTPException(
            status_code=400,
            detail=f"project_id must be a positive integer, got {raw_project_id!r}",
        )
    messages = body.get("messages", [])
    messages, user_text, raw_user_text, explicit_context_block, explicit_context_warnings = (
        _prepare_explicit_context(messages)
    )
    stream = body.get("stream", True)
    # A caller that sends tool schemas is the one that executes the calls —
    # Open WebUI does exactly this. Kitty has no executor of its own here, so the
    # schemas and the "tools are unavailable" instruction both hinge on this.
    caller_supplies_tools = bool(body.get("tools"))

    turn_has_image = False
    for m in reversed(messages):
        if m.get("role") == "user":
            turn_has_image = _has_image(m.get("content", ""))
            break

    raw_attachment_ids = body.get("attachment_ids")
    if raw_attachment_ids is not None:
        if not isinstance(raw_attachment_ids, list) or not all(
            isinstance(a, str) for a in raw_attachment_ids
        ):
            raise HTTPException(
                status_code=400, detail="attachment_ids must be a list of strings"
            )
        attachment_ids = [a for a in raw_attachment_ids if a.strip()]
    else:
        attachment_ids = None
    raw_image_attachment_ids = body.get("image_attachment_ids")
    if raw_image_attachment_ids is not None:
        if not isinstance(raw_image_attachment_ids, list) or not all(
            isinstance(a, str) for a in raw_image_attachment_ids
        ):
            raise HTTPException(
                status_code=400,
                detail="image_attachment_ids must be a list of strings",
            )
        image_attachment_ids = [a.strip() for a in raw_image_attachment_ids if a.strip()]
        if len(image_attachment_ids) != 1:
            raise HTTPException(
                status_code=400,
                detail="image_attachment_ids must contain exactly one nonblank id",
            )
        if attachment_ids is None or image_attachment_ids[0] not in attachment_ids:
            raise HTTPException(
                status_code=400,
                detail="image_attachment_ids must reference an attachment_ids entry",
            )
        turn_has_image = True
    else:
        image_attachment_ids = None

    # KX-05-02 / KX-06-01: detect repairs/signals intent and inject the current feed
    if _is_repairs_intent(user_text):
        repairs_context = _build_repairs_context()
        signals_context = _build_signals_context()
        combined: list[str] = []
        if repairs_context:
            combined.append(repairs_context)
        if signals_context:
            combined.append(signals_context)
        if combined:
            messages = [{"role": "system", "content": "\n\n".join(combined)}] + list(messages)

    correlation_id = str(uuid.uuid4())[:8]
    t_start = time.monotonic()

    manifest_task = asyncio.create_task(compose_manifest(project_id=raw_project_id))

    domain = classify_domain(user_text)
    from gateway.reasoning import classify_complexity

    classification = classify_complexity(user_text, domain=domain)

    try:
        runtime_manifest = await manifest_task
    except Exception:
        on_request_error()
        raise
    tier = classification.tier
    trigger = classification.trigger
    t_classified = time.monotonic()
    logger.info(
        "chat %s: pre-processing %dms (tier=%s trigger=%s)",
        correlation_id,
        int((t_classified - t_start) * 1000),
        tier,
        trigger,
    )
    requested_model = body.get("model", "kitty-default")
    # reroute_virtual_models lets "Kitty Auto" mean what it says: the classifier
    # picks the tier. Every other menu id is a pin the caller chose, and stays.
    route_decision = resolve_chat_route(
        requested_model,
        user_text,
        reroute_virtual_models=True,
        domain=domain,
        has_image=turn_has_image,
    )
    # route_model stays in the auto path: it is the seam callers and tests patch
    # to redirect routing, and reading route_decision.model directly would walk
    # straight past it.
    # route_model stays the patchable seam for the plain text-auto path, but a
    # modality decision already knows better than a re-classification can.
    model = (
        route_decision.model
        if route_decision.source in {"request", "modality"}
        else route_model(user_text)
    )

    conversation_id = body.get("conversation_id")
    if conversation_id is not None and (
        not isinstance(conversation_id, str) or not conversation_id.strip()
    ):
        raise HTTPException(status_code=400, detail="conversation_id must be a non-empty string")
    user_message_id = body.get("user_message_id")
    if user_message_id is not None and not isinstance(user_message_id, str):
        raise HTTPException(status_code=400, detail="user_message_id must be a string")
    conversation_title = body.get("conversation_title", "")
    if not isinstance(conversation_title, str):
        raise HTTPException(status_code=400, detail="conversation_title must be a string")
    manifest_project = runtime_manifest["context"]["active_project"]["value"]
    scoped_project_id = raw_project_id
    if scoped_project_id is None and isinstance(manifest_project, dict):
        candidate_project_id = manifest_project.get("id")
        if isinstance(candidate_project_id, int) and not isinstance(candidate_project_id, bool):
            scoped_project_id = candidate_project_id

    lifecycle_handle: chat_lifecycle.TurnHandle | None = None
    lifecycle_done = False
    thread_objective: str | None = None
    if conversation_id is not None:
        try:
            chat = chats_store.get_chat(conversation_id)
            if chat is not None:
                stored_objective = chat.get("objective")
                if stored_objective is not None and not isinstance(stored_objective, str):
                    raise RuntimeError(
                        f"chat {conversation_id!r} has a non-string objective"
                    )
                thread_objective = stored_objective
            lifecycle_handle = chat_lifecycle.start_turn(
                conversation_id=conversation_id,
                project_id=scoped_project_id,
                title=conversation_title,
                user_message_id=user_message_id,
                user_text=raw_user_text or user_text,
                manifest_revision=runtime_manifest["revision"],
                requested_model=model,
                attachment_ids=attachment_ids,
                objective=thread_objective,
            )
        except Exception:
            on_request_error()
            raise

    resolved_parts: list[dict] = []
    if image_attachment_ids:
        try:
            resolved_parts = _resolve_attachment_image_parts(image_attachment_ids)
        except HTTPException as exc:
            if lifecycle_handle is not None and not lifecycle_done:
                _finish_lifecycle_or_raise(
                    lifecycle_handle,
                    status="failed",
                    assistant_text="",
                    error=(
                        f"attachment resolution failed ({exc.status_code}): "
                        f"{exc.detail}"
                    ),
                )
                lifecycle_done = True
            on_request_error()
            raise HTTPException(
                status_code=exc.status_code,
                detail={"kind": "attachment", "message": _ATTACHMENT_FAILURE_MESSAGE},
            ) from exc
        except Exception as exc:
            if lifecycle_handle is not None and not lifecycle_done:
                _finish_lifecycle_or_raise(
                    lifecycle_handle,
                    status="failed",
                    assistant_text="",
                    error=f"attachment resolution failed: {exc}",
                )
                lifecycle_done = True
            on_request_error()
            raise HTTPException(
                status_code=400,
                detail={"kind": "attachment", "message": _ATTACHMENT_FAILURE_MESSAGE},
            ) from exc

    from gateway.context_assembler import (
        TOTAL_CONTEXT_TOKEN_CAPS,
        SelectedSkillTooLargeError,
        SkillSelectionError,
        assemble_context,
        assert_not_total_failure,
    )

    try:
        on_context_fetch()
        bundle = await assemble_context(
            user_text,
            parts_mode=False,
            domain=domain,
            objective=thread_objective,
            tier=tier,
        )
        assert_not_total_failure(bundle)
        if explicit_context_warnings:
            bundle.warnings.extend(
                f"explicit_context: {warning}" for warning in explicit_context_warnings
            )
        bundle_system = bundle.system
        if explicit_context_block:
            bundle_system = f"{bundle_system}\n\n{explicit_context_block}"
        runtime_system = compact_runtime_context(runtime_manifest)
        tool_system = "" if caller_supplies_tools else _NO_TOOL_EXECUTOR_SYSTEM
        enriched, final_budget_warnings = _fit_final_model_messages(
            bundle_system=bundle_system,
            runtime_system=runtime_system,
            tool_system=tool_system,
            messages=messages,
            token_cap=TOTAL_CONTEXT_TOKEN_CAPS[tier],
        )
        bundle.warnings.extend(final_budget_warnings)
        for warning in final_budget_warnings:
            logger.warning("chat %s: %s", correlation_id, warning)
        system_prompt = (
            str(enriched[0].get("content", ""))
            if enriched and enriched[0].get("role") == "system"
            else ""
        )
        selected_skill_block = getattr(bundle, "selected_skill_block", None)
        if (
            isinstance(selected_skill_block, str)
            and selected_skill_block
            and selected_skill_block not in system_prompt
        ):
            raise SelectedSkillTooLargeError(
                "Selected skill instructions cannot fit alongside the current chat context"
            )
    except Exception as exc:
        if lifecycle_handle is not None and not lifecycle_done:
            _finish_lifecycle_or_raise(
                lifecycle_handle,
                status="failed",
                assistant_text="",
                error=str(exc),
            )
            lifecycle_done = True
        on_request_error()
        if isinstance(exc, SkillSelectionError):
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if isinstance(exc, SelectedSkillTooLargeError):
            raise HTTPException(status_code=413, detail=str(exc)) from exc
        raise

    stripped = {
        # content_class is a legacy D10 field (ADR 0022). It no longer routes
        # anything, but keep filtering it so an old client can't leak it upstream.
        "project_id",
        "conversation_id",
        "conversation_title",
        "user_message_id",
        "content_class",
        "image_attachment_ids",
    }
    if not caller_supplies_tools:
        # Nothing on this side executes a tool call, so an unaccompanied schema
        # would only invite one Kitty cannot complete.
        stripped |= {"tools", "tool_choice", "parallel_tool_calls"}

    payload = {
        **{key: value for key, value in body.items() if key not in stripped},
        "messages": enriched,
        "model": model,
        "stream": stream,
    }

    if resolved_parts:
        payload["messages"] = _attach_images_to_user_message(
            payload["messages"], resolved_parts
        )

    selected_provider = selected_provider_name()
    provider_label = selected_provider or "auto"
    upstream_chars = sum(
        len(str(message.get("content", "")))
        for message in enriched
        if isinstance(message, dict)
    )
    logger.info(
        "chat %s: request_trace %s",
        correlation_id,
        json.dumps(
  {
      "conversation_id": conversation_id,
      "provider_selected": provider_label,
      "client_model_requested": route_decision.requested_model,
      "model_routed": model,
      "message_count": len(enriched),
      "message_content_chars": upstream_chars,
      "system_prompt_chars": len(system_prompt),
      "memory_items_injected": len(bundle.injected_memory_items),
      "preprocessing_ms": int((time.monotonic() - t_start) * 1000),
      "tool_execution": "caller" if caller_supplies_tools else "unavailable",
  },
  sort_keys=True,
        ),
    )

    if stream:
        # Memory-evidence trailer (CR-04): built before streaming starts so
        # the hot path only pays a byte comparison per chunk. None when no
        # memories were injected — the trailer must then be absent.
        trailer_items: list[MemoryEvidence] | None = None
        memory_trailer: bytes | None = None
        if bundle.injected_memory_items:
            # Full injected texts, untruncated (Jacob, 2026-07-20): the render
            # budget already bounds them, and a mid-sentence chop reads worse
            # than a longer line in the "kitty remembered" block.
            trailer_items = list(bundle.injected_memory_items)
            trailer_json = json.dumps(
                {"memory_items": trailer_items}, ensure_ascii=False
            )
            memory_trailer = b"data: " + trailer_json.encode("utf-8") + b"\n\n"

        async def stream_with_trace():
            nonlocal lifecycle_done
            accumulated = ""
            trailer = memory_trailer
            first_chunk = True
            try:
                async for chunk in iter_chat_completions_stream(payload):
                    if first_chunk and chunk.startswith(b"data: "):
                        raw = chunk[6:].strip()
                        if raw != b"[DONE]":
                            t_first = time.monotonic()
                            logger.info(
                                "chat %s: ttft %dms",
                                correlation_id,
                                int((t_first - t_start) * 1000),
                            )
                            first_chunk = False
                    # The trailer rides immediately before the upstream [DONE].
                    # A stream that never reaches [DONE] (error, cancellation,
                    # cut connection) gets no memory evidence.
                    if (
                        trailer is not None
                        and chunk.startswith(b"data: ")
                        and chunk[6:].strip() == b"[DONE]"
                    ):
                        yield trailer
                        trailer = None
                    yield chunk
                    if lifecycle_handle is not None and chunk.startswith(b"data: "):
                        raw_chunk = chunk[6:].strip()
                        if raw_chunk != b"[DONE]":
                            chunk_payload = json.loads(raw_chunk)
                            choices = chunk_payload.get("choices")
                            if not isinstance(choices, list) or not choices:
                                raise RuntimeError(
                                    "stream chunk omitted choices while recording chat lifecycle"
                                )
                            delta = choices[0].get("delta")
                            if not isinstance(delta, dict):
                                raise RuntimeError(
                                    "stream chunk omitted delta while recording chat lifecycle"
                                )
                            content = delta.get("content", "")
                            if not isinstance(content, str):
                                raise RuntimeError(
                                    "stream chunk content was not text while recording chat lifecycle"
                                )
                            accumulated += content
                if lifecycle_handle is not None:
                    # Ledger evidence mirrors the wire exactly: recorded only
                    # when the trailer was actually delivered to the client.
                    trailer_emitted = memory_trailer is not None and trailer is None
                    _finish_lifecycle_or_raise(
                        lifecycle_handle,
                        status="succeeded",
                        assistant_text=accumulated,
                        resolved_model=model,
                        memory_items=trailer_items if trailer_emitted else None,
                    )
                    lifecycle_done = True
                log_chat_trace(
                    LOG_FILE,
                    correlation_id,
                    user_text,
                    domain,
                    model,
                    t_start,
                    runtime_revision=runtime_manifest["revision"],
                    tier=tier,
                    trigger=trigger,
                )
                on_request_success()
            except Exception as exc:
                chat_turn_error = isinstance(exc, ChatTurnError)
                if lifecycle_handle is not None and not lifecycle_done:
                    # Persist the truthful failure into the ledger. An empty
                    # finish_turn inserts no assistant message (chat_lifecycle),
                    # so a provider rejection with zero content would silently
                    # vanish on restart — instead record the user-facing copy so
                    # restart/resume keeps showing the failed turn with retry.
                    failure_content = accumulated or (
                        exc.message if chat_turn_error else ""
                    )
                    _finish_lifecycle_or_raise(
                        lifecycle_handle,
                        status=("failed" if chat_turn_error else "interrupted"),
                        assistant_text=failure_content,
                        resolved_model=model,
                        error=(exc.detail if chat_turn_error else str(exc)),
                    )
                    lifecycle_done = True
                # One user-facing error event before the stream tears down, so
                # the phone gets a plain-language cause + recovery instead of a
                # bare connection drop (#346 Chat trust baseline).
                yield sse_error_event(
                    exc.kind if chat_turn_error else ChatErrorKind.UPSTREAM,
                    exc.message if chat_turn_error else FRIENDLY_MESSAGES[ChatErrorKind.UPSTREAM],
                )
                on_request_error()
                raise

        lifecycle_headers = {
            "X-Kitty-Runtime-Revision": runtime_manifest["revision"],
            "X-Kitty-Model-Selected": model,
            "X-Kitty-Model-Requested": str(route_decision.requested_model),
            "X-Kitty-Provider-Selected": provider_label,
            "X-Kitty-Tools-State": "caller" if caller_supplies_tools else "unavailable",
        }
        if lifecycle_handle is not None:
            lifecycle_headers["X-Kitty-Turn-ID"] = lifecycle_handle.turn_id
            lifecycle_headers["X-Kitty-Attempt-ID"] = lifecycle_handle.attempt_id
        return StreamingResponse(
            stream_with_trace(),
            media_type="text/event-stream",
            headers=lifecycle_headers,
        )

    try:
        result = await chat_completions_non_stream(payload)
        resolved_model = result.get("model") or model
        # Memory-evidence parity with the streaming trailer (C4-07): the
        # non-stream path used to record and return no memory evidence at
        # all, even when the same bundle injected memories into the prompt.
        non_stream_memory_items: list[MemoryEvidence] | None = (
            list(bundle.injected_memory_items) if bundle.injected_memory_items else None
        )
        if lifecycle_handle is not None:
            _finish_lifecycle_or_raise(
                lifecycle_handle,
                status="succeeded",
                assistant_text=_assistant_text_from_result(result),
                resolved_model=resolved_model,
                memory_items=non_stream_memory_items,
            )
            lifecycle_done = True
        log_chat_trace(
            LOG_FILE,
            correlation_id,
            user_text,
            domain,
            model,
            t_start,
            runtime_revision=runtime_manifest["revision"],
            model_resolved=resolved_model,
            tier=tier,
            trigger=trigger,
        )
        on_request_success()
        response = {
            **result,
            "kitty_runtime": {
                "manifest_revision": runtime_manifest["revision"],
                "resolved_model": resolved_model,
            },
        }
        if non_stream_memory_items:
            response["memory_items"] = non_stream_memory_items
        return response
    except Exception as exc:
        if lifecycle_handle is not None and not lifecycle_done:
            _finish_lifecycle_or_raise(
                lifecycle_handle,
                status="failed",
                assistant_text="",
                error=str(exc),
            )
            lifecycle_done = True
        on_request_error()
        raise


@router.post("/api/chat/completions")
async def api_chat_completions(request: Request):
    """Open WebUI-compatible alias so kitty-chat can target the gateway directly."""
    return await chat_completions(request)


@router.get("/api/models")
async def api_models():
    """Return available models with display names resolved from the routing config."""
    from gateway.model_routing import describe_routing

    routing = describe_routing()
    alias_map = {r["alias"]: r["upstream_model"] for r in routing.get("routes", []) if r.get("alias")}

    client = await get_http_client()
    try:
        resp = await client.get(
            f"{LITELLM_BASE}/v1/models",
            headers={"Authorization": f"Bearer {LITELLM_KEY}"},
        )
        if resp.status_code != 200:
            detail = getattr(resp, "text", "")[:500]
            raise HTTPException(
                status_code=502,
                detail=(
                    f"LiteLLM model discovery returned HTTP {resp.status_code}"
                    + (f": {detail}" if detail else "")
                ),
            )

        data = resp.json()
        models = data.get("data", [])
        for model in models:
            alias = model.get("id", "")
            upstream = alias_map.get(alias, "")
            if upstream:
                model["display_name"] = upstream.split("/")[-1]

        return data

    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("Failed to fetch models from LiteLLM: %s", exc)
        raise HTTPException(
            status_code=502,
            detail=f"LiteLLM model discovery failed: {exc}",
        ) from exc


@router.get("/api/model-routing")
async def api_model_routing():
    """Which provider each kitty-* alias actually calls, and whether its key is set.

    /api/models only returns alias ids, which is why an out-of-credit provider
    was indistinguishable from a healthy one everywhere in the UI.
    """
    from gateway.model_routing import describe_routing

    return describe_routing()


@router.get("/api/providers")
async def api_providers():
    """The direct-call fallback chain — order, key state, and what's disabled."""
    from gateway.model_routing import describe_providers

    return describe_providers()


class ProviderPrefsRequest(BaseModel):
    order: list[str] = Field(default_factory=list)
    disabled: list[str] = Field(default_factory=list)
    active: str = "auto"


@router.post("/api/providers")
async def api_providers_set(payload: ProviderPrefsRequest):
    """Reorder or disable providers without editing Python or restarting."""
    from gateway.llm_client import PROVIDERS
    from gateway.model_routing import describe_providers
    from gateway.provider_prefs import save_preferences

    try:
        save_preferences(
            payload.order,
            payload.disabled,
            known=tuple(PROVIDERS.keys()),
            active=payload.active,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return describe_providers()


@router.post("/sessions/close")
async def close_session(payload: CloseSessionRequest):
    """End a chat session — consolidate short-term memory to long-term."""
    from gateway.memory import consolidate_session

    consolidate_session(payload.session_id, payload.messages)
    return {"status": "ok", "session_id": payload.session_id}


_REPAIRS_INTENT_PATTERNS = [
    "what's wrong",
    "what is wrong",
    "anything broken",
    "is anything wrong",
    "is something wrong",
    "any issues",
    "system health",
    "run diagnostics",
    "check the system",
    "how's the system",
    "what needs fixing",
    "any problems",
    "anything to flag",
    "what's up",
    "any signals",
    "what should I know",
]


def _is_repairs_intent(user_text: str) -> bool:
    lower = user_text.strip().lower()
    return any(pattern in lower for pattern in _REPAIRS_INTENT_PATTERNS)


def _build_signals_context() -> str | None:
    """Build a plain-English signals summary for chat injection."""
    try:
        from gateway import signal_store
        signals = signal_store.list_unprocessed(limit=20)
        if not signals:
            return None
        lines = ["Active signals from your system:"]
        for s in signals:
            payload = s.get("payload") or {}
            title = payload.get("title") or s.get("source", "unknown")
            text = payload.get("text") or payload.get("summary") or ""
            tag = s.get("source", "").replace("expert.", "")
            lines.append(f"  [{tag}] {title}")
            if text:
                lines.append(f"    {text[:200]}")
        return "\n".join(lines)
    except Exception:
        return None


def _build_repairs_context() -> str | None:
    import pathlib
    import sys

    ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
    sys.path.insert(0, str(ROOT))

    try:
        from gateway.doctor import (
            Check,
            _check_codegraph,
            _check_disk,
            _check_env,
            _check_gateway_freshness,
            _check_mem0,
            _check_services,
            _check_venv,
            _load_env,
        )
        from gateway.routes.repairs import _to_repair

        env = _load_env()
        checks: list[Check] = []
        checks.extend(_check_env(env))
        checks.extend(_check_disk())
        checks.extend(_check_services(env))
        checks.extend(_check_mem0(env))
        checks.extend(_check_venv())
        checks.extend(_check_codegraph())
        checks.extend(_check_gateway_freshness())

        repairs = [_to_repair(c) for c in checks]
        issues = [r for r in repairs if r["severity"] != "ok"]
        all_ok = len(issues) == 0

        lines = ["You are Kitty's self-diagnosis system. The user asked what's wrong with the system. Here is the current status:"]
        if all_ok:
            lines.append("All systems are healthy — {0} checks passed with no issues. Tell the user everything is running fine.".format(len(repairs)))
        else:
            lines.append("{0} issues found out of {1} checks:".format(len(issues), len(repairs)))
            for item in issues:
                sev = {"ok": "OK", "warn": "WARNING", "error": "ERROR"}.get(item["severity"], "UNKNOWN")
                lines.append("  [{0}] {1} — {2}".format(sev, item["title"], item["detail"]))
                if item.get("fix"):
                    fix = item["fix"]
                    lines.append("    Fix available: {0}".format(fix["label"]))
            lines.append("Summarize the issues for the user in plain English. For each issue, mention the fix if one is available. Do not use file paths or CLI commands in your answer.")

        # Also inject a listing of fixes that work through the action queue
        lines.append("")
        lines.append("Fix buttons are available in the Home view under the System card. The /repairs endpoint re-checks each issue and the action queue records every fix.")

        return "\n".join(lines)
    except Exception as exc:
        logger.warning("Failed to build repairs context: %s", exc)
        return None
