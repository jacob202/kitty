"""LiteLLM chat-completions proxy."""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from typing import Mapping, cast

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response, StreamingResponse

from gateway import chat_lifecycle, chats_store
from gateway.chat_errors import (
    FRIENDLY_MESSAGES,
    ChatErrorKind,
    ChatTurnError,
    sse_error_event,
)
from gateway.completion_prep import (
    _ATTACHMENT_FAILURE_MESSAGE,
    _CURRENT_VERIFICATION_ABSTENTION,
    _CURRENT_VERIFICATION_POLICY_MODEL,
    _NO_TOOL_EXECUTOR_SYSTEM,
    _attach_builder_results_to_user_message,
    _attach_images_to_user_message,
    _build_repairs_context,
    _build_signals_context,
    _durable_chat_object_system,
    _fit_final_model_messages,
    _has_current_source_tool,
    _has_image,
    _is_repairs_intent,
    _prepare_explicit_context,
    _resolve_attachment_image_parts,
    _resolve_builder_result_attachments,
    _static_abstention_result,
    _static_abstention_stream,
)
from gateway.constants import MAX_BODY_BYTES
from gateway.domain_router import classify_domain
from gateway.llm_client import (
    chat_completions_non_stream,
    iter_chat_completions_stream,
    log_chat_trace,
    selected_provider_name,
)
from gateway.memory_graph import MemoryEvidence
from gateway.model_routing import resolve_chat_route
from gateway.paths import LOG_FILE
from gateway.runtime_manifest import compact_runtime_context, compose_manifest

logger = logging.getLogger("kitty.gateway")
router = APIRouter(tags=["completions"])


def route_model(message: str) -> str:
    """Compatibility routing seam for tests and callers that still patch this Module."""
    return resolve_chat_route("kitty-default", message, reroute_virtual_models=True).model


def _finish_lifecycle_or_raise(
    handle: chat_lifecycle.TurnHandle,
    *,
    status: str,
    assistant_text: str,
    resolved_model: str | None = None,
    error: str | None = None,
    memory_items: list[MemoryEvidence] | None = None,
    evidence_items: list[dict[str, str]] | None = None,
) -> None:
    try:
        chat_lifecycle.finish_turn(
            handle,
            status=status,
            assistant_text=assistant_text,
            resolved_model=resolved_model,
            error=error,
            memory_items=memory_items,
            evidence_items=evidence_items,
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
    raw_expert_id = body.get("expert_id")
    if raw_expert_id is not None and (
        not isinstance(raw_expert_id, str) or not raw_expert_id.strip()
    ):
        raise HTTPException(status_code=400, detail="expert_id must be a non-empty string")
    expert_id = raw_expert_id.strip() if isinstance(raw_expert_id, str) else None
    if expert_id:
        from gateway import knowledge

        try:
            knowledge.require_active_corpus_expert(expert_id)
        except knowledge.UnknownCorpusExpertError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except knowledge.CorpusProjectionUnavailableError as exc:
            raise HTTPException(
                status_code=503, detail="Expert sources are unavailable right now."
            ) from exc

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
    messages, user_text, raw_user_text, explicit_context_warnings = (
        _prepare_explicit_context(messages)
    )
    stream = body.get("stream", True)
    # A caller that sends tool schemas is the one that executes the calls —
    # Open WebUI does exactly this. Kitty has no executor of its own here, so the
    # schemas and the "tools are unavailable" instruction both hinge on this.
    caller_supplies_tools = bool(body.get("tools"))
    current_source_tool_available = _has_current_source_tool(
        body.get("tools"), body.get("tool_choice")
    )

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
    if expert_id and tier == "trivial":
        # Selecting an expert is an explicit request for source-grounded context.
        tier = "standard"
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

    resolved_builder_results: list[dict] = []
    if attachment_ids:
        try:
            resolved_builder_results = _resolve_builder_result_attachments(attachment_ids)
            if resolved_builder_results:
                messages = _attach_builder_results_to_user_message(messages, resolved_builder_results)
        except HTTPException as exc:
            if lifecycle_handle is not None and not lifecycle_done:
                _finish_lifecycle_or_raise(
                    lifecycle_handle,
                    status="failed",
                    assistant_text="",
                    error=f"Builder result attachment resolution failed ({exc.status_code}): {exc.detail}",
                )
                lifecycle_done = True
            on_request_error()
            raise HTTPException(
                status_code=exc.status_code,
                detail={
                    "kind": "attachment",
                    "message": "Kitty couldn't use that saved Builder result. Remove it and stage it again.",
                },
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
            expert_profile=expert_id,
        )
        assert_not_total_failure(bundle)
        if explicit_context_warnings:
            bundle.warnings.extend(
                f"explicit_context: {warning}" for warning in explicit_context_warnings
            )
        bundle_system = bundle.system
        runtime_system = compact_runtime_context(runtime_manifest)
        project_name = (
            manifest_project.get("name")
            if isinstance(manifest_project, dict) and isinstance(manifest_project.get("name"), str)
            else None
        )
        durable_object_system = _durable_chat_object_system(
            conversation_id=conversation_id,
            user_message_id=user_message_id,
            project_id=scoped_project_id,
            project_name=project_name,
        )
        tool_system = "" if caller_supplies_tools else _NO_TOOL_EXECUTOR_SYSTEM
        enriched, final_budget_warnings = _fit_final_model_messages(
            bundle_system=bundle_system,
            runtime_system=runtime_system,
            tool_system=tool_system,
            optional_system=durable_object_system,
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
        selected_expert_evidence_block = getattr(bundle, "selected_expert_evidence_block", None)
        if (
            isinstance(selected_expert_evidence_block, str)
            and selected_expert_evidence_block
            and selected_expert_evidence_block not in system_prompt
        ):
            raise HTTPException(
                status_code=413,
                detail="Selected expert evidence cannot fit alongside the current chat context",
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
        "expert_id",
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

    if resolved_builder_results and isinstance(payload.get("attachment_ids"), list):
        resolved_ids = {str(item["id"]) for item in resolved_builder_results}
        remaining_ids = [
            artifact_id
            for artifact_id in payload["attachment_ids"]
            if artifact_id not in resolved_ids
        ]
        if remaining_ids:
            payload["attachment_ids"] = remaining_ids
        else:
            payload.pop("attachment_ids", None)

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
      "expert_profile": expert_id,
      "preprocessing_ms": int((time.monotonic() - t_start) * 1000),
      "tool_execution": "caller" if caller_supplies_tools else "unavailable",
  },
  sort_keys=True,
        ),
    )

    must_abstain_for_current_verification = (
        bundle.evidence_policy.current_verification_required and not current_source_tool_available
    )
    if must_abstain_for_current_verification:
        abstention = _CURRENT_VERIFICATION_ABSTENTION
        if lifecycle_handle is not None:
            _finish_lifecycle_or_raise(
                lifecycle_handle,
                status="succeeded",
                assistant_text=abstention,
                resolved_model=_CURRENT_VERIFICATION_POLICY_MODEL,
            )
            lifecycle_done = True
        log_chat_trace(
            LOG_FILE,
            correlation_id,
            user_text,
            domain,
            _CURRENT_VERIFICATION_POLICY_MODEL,
            t_start,
            runtime_revision=runtime_manifest["revision"],
            model_resolved=_CURRENT_VERIFICATION_POLICY_MODEL,
            tier=tier,
            trigger=trigger,
        )
        on_request_success()
        headers = {
            "X-Kitty-Runtime-Revision": runtime_manifest["revision"],
            "X-Kitty-Model-Selected": _CURRENT_VERIFICATION_POLICY_MODEL,
            "X-Kitty-Model-Requested": str(route_decision.requested_model),
            "X-Kitty-Provider-Selected": "policy",
            "X-Kitty-Tools-State": "unavailable",
            "X-Kitty-Current-Verification": "required-unavailable",
        }
        if lifecycle_handle is not None:
            headers["X-Kitty-Turn-ID"] = lifecycle_handle.turn_id
            headers["X-Kitty-Attempt-ID"] = lifecycle_handle.attempt_id
        if stream:
            async def abstention_stream():
                for chunk in _static_abstention_stream(abstention):
                    yield chunk

            return StreamingResponse(
                abstention_stream(),
                media_type="text/event-stream",
                headers=headers,
            )
        response = _static_abstention_result(abstention)
        response["kitty_runtime"] = {
            "manifest_revision": runtime_manifest["revision"],
            "resolved_model": _CURRENT_VERIFICATION_POLICY_MODEL,
            "current_verification": "required_unavailable",
        }
        return response

    if stream:
        # One truthful metadata trailer rides immediately before [DONE]. It
        # contains only evidence records that actually reached the model prompt.
        trailer_memory_items: list[MemoryEvidence] | None = (
            list(bundle.injected_memory_items) if bundle.injected_memory_items else None
        )
        trailer_evidence_items: list[dict[str, str]] | None = (
            [dict(cast(Mapping[str, str], item)) for item in bundle.injected_evidence_items]
            if bundle.injected_evidence_items
            else None
        )
        trailer_payload: dict[str, object] = {}
        if trailer_memory_items:
            trailer_payload["memory_items"] = trailer_memory_items
        if trailer_evidence_items:
            trailer_payload["evidence_items"] = trailer_evidence_items
        metadata_trailer: bytes | None = None
        if trailer_payload:
            trailer_json = json.dumps(trailer_payload, ensure_ascii=False)
            metadata_trailer = b"data: " + trailer_json.encode("utf-8") + b"\n\n"

        async def stream_with_trace():
            nonlocal lifecycle_done
            accumulated = ""
            trailer = metadata_trailer
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
                    trailer_emitted = metadata_trailer is not None and trailer is None
                    _finish_lifecycle_or_raise(
                        lifecycle_handle,
                        status="succeeded",
                        assistant_text=accumulated,
                        resolved_model=model,
                        memory_items=trailer_memory_items if trailer_emitted else None,
                        evidence_items=trailer_evidence_items if trailer_emitted else None,
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
        non_stream_evidence_items: list[dict[str, str]] | None = (
            [dict(cast(Mapping[str, str], item)) for item in bundle.injected_evidence_items]
            if bundle.injected_evidence_items
            else None
        )
        if lifecycle_handle is not None:
            _finish_lifecycle_or_raise(
                lifecycle_handle,
                status="succeeded",
                assistant_text=_assistant_text_from_result(result),
                resolved_model=resolved_model,
                memory_items=non_stream_memory_items,
                evidence_items=non_stream_evidence_items,
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
        if non_stream_evidence_items:
            response["evidence_items"] = non_stream_evidence_items
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

