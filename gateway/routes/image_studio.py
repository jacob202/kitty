"""Image Studio routes.

Split from the former routes/extended.py on 2026-09-16 so each route module
owns one domain (architecture claim: "Routes should remain thin").
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, HTTPException, UploadFile
from pydantic import BaseModel

router = APIRouter(tags=["studio"])


# --- Image Studio V1: Characters ---


class CharacterCreate(BaseModel):
    name: str
    description: Optional[str] = None
    preferred_recipe: Optional[str] = None
    identity_preset: str = "balanced"


class CharacterUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    preferred_recipe: Optional[str] = None
    identity_preset: Optional[str] = None


class RecipeUpdate(BaseModel):
    available: bool


class StudioGenerateRequest(BaseModel):
    prompt: str
    quality: str = "quality"
    identity: str = "balanced"
    character_id: Optional[str] = None
    recipe_id: Optional[str] = None
    negative_prompt: Optional[str] = None
    plan_id: Optional[str] = None
    session_id: Optional[str] = None


class PlanPreviewRequest(BaseModel):
    """Preview a generation plan before committing to generation.

    *content_lane*/*consent_basis*/*adult_confirmed* are the trusted policy
    declaration (ADR 0040 #8) persisted with the approved plan. They default
    to the safe lane, and private_adult cannot be inferred from prompt text.
    """
    prompt: str
    character_id: Optional[str] = None
    recipe_id: Optional[str] = None
    guidance_tags: Optional[List[str]] = None
    session_id: Optional[str] = None
    content_lane: Optional[str] = None
    consent_basis: Optional[str] = None
    adult_confirmed: bool = False


@router.get("/studio/characters")
async def studio_list_characters():
    from gateway.image_characters import list_characters

    chars = list_characters()
    return {"characters": [c.to_dict() for c in chars]}


@router.post("/studio/characters")
async def studio_create_character(req: CharacterCreate):
    from gateway.image_characters import CharacterError, create_character
    try:
        char = create_character(
            name=req.name,
            description=req.description,
            preferred_recipe=req.preferred_recipe,
            identity_preset=req.identity_preset,
        )
        return char.to_dict()
    except CharacterError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/studio/characters/{character_id}")
async def studio_get_character(character_id: str):
    from gateway.image_characters import CharacterNotFoundError, get_character, list_character_refs
    try:
        char = get_character(character_id)
        refs = list_character_refs(character_id)
        result = char.to_dict()
        result["references"] = [r.to_dict() for r in refs]
        return result
    except CharacterNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.patch("/studio/characters/{character_id}")
async def studio_update_character(character_id: str, req: CharacterUpdate):
    from gateway import undo_journal
    from gateway.image_characters import CharacterError, CharacterNotFoundError, get_character
    try:
        journal_id = undo_journal.update_character_with_undo(
            character_id,
            name=req.name,
            description=req.description,
            preferred_recipe=req.preferred_recipe,
            identity_preset=req.identity_preset,
        )
        result = get_character(character_id).to_dict()
        result["undo_journal_id"] = journal_id
        return result
    except CharacterNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except CharacterError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete("/studio/characters/{character_id}")
async def studio_delete_character(character_id: str):
    from gateway.image_characters import CharacterNotFoundError, soft_delete_character
    try:
        char = soft_delete_character(character_id)
        return char.to_dict()
    except CharacterNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/studio/characters/{character_id}/references")
async def studio_add_character_ref(character_id: str, file: UploadFile):
    from gateway.image_characters import CharacterError, CharacterNotFoundError, add_character_ref
    from gateway.image_quality import check_reference_image

    data = await file.read()
    if len(data) > 20 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="file too large (max 20 MB)")
    try:
        quality = check_reference_image(data)
        quality_notes = quality.summary()
        ref = add_character_ref(
            character_id, data,
            original_name=file.filename,
            media_type=file.content_type,
            quality_notes=quality_notes,
        )
        result = ref.to_dict()
        result["quality"] = {
            "has_blockers": quality.has_blockers,
            "has_warnings": quality.has_warnings,
            "is_perfect": quality.is_perfect,
            "summary": quality.summary(),
            "advice": quality.advice(),
            "dimensions": f"{quality.width}×{quality.height}" if quality.width else None,
        }
        return result
    except CharacterNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except CharacterError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/studio/characters/{character_id}/quality")
async def studio_character_quality(character_id: str):
    from gateway.image_characters import CharacterNotFoundError, get_character, list_character_refs
    from gateway.image_quality import check_reference_image

    try:
        get_character(character_id)
        refs = list_character_refs(character_id)
    except CharacterNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    if not refs:
        return {"quality": None, "message": "no reference images uploaded"}

    results = []
    for ref in refs:
        try:
            path = Path(ref.storage_path)
            if path.exists():
                data = path.read_bytes()
                qr = check_reference_image(data)
                results.append({
                    "ref_id": ref.ref_id,
                    "is_primary": ref.is_primary,
                    "original_name": ref.original_name,
                    "has_blockers": qr.has_blockers,
                    "has_warnings": qr.has_warnings,
                    "is_perfect": qr.is_perfect,
                    "summary": qr.summary(),
                    "advice": qr.advice(),
                    "dimensions": f"{qr.width}×{qr.height}" if qr.width else None,
                })
        except Exception:
            results.append({
                "ref_id": ref.ref_id,
                "is_primary": ref.is_primary,
                "original_name": ref.original_name,
                "has_blockers": True,
                "has_warnings": False,
                "is_perfect": False,
                "summary": "could not read reference file",
                "advice": ["the reference file may be missing or corrupted"],
                "dimensions": None,
            })

    return {"quality": results}


@router.delete("/studio/characters/{character_id}/references/{ref_id}")
async def studio_delete_character_ref(character_id: str, ref_id: str):
    from gateway.image_characters import (
        CharacterError,
        CharacterNotFoundError,
        delete_character_ref,
    )
    try:
        delete_character_ref(character_id, ref_id)
        return {"deleted": True}
    except CharacterNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except CharacterError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# --- Image Studio V1: Recipes ---

@router.get("/studio/recipes")
async def studio_list_recipes(available_only: bool = False):
    from gateway.image_recipes import list_recipes
    recipes = list_recipes(available_only=available_only)
    return {"recipes": [r.to_dict() for r in recipes]}


@router.patch("/studio/recipes/{recipe_id}")
async def studio_update_recipe(recipe_id: str, req: RecipeUpdate):
    from gateway.image_recipes import RecipeError, set_recipe_available
    try:
        recipe = set_recipe_available(recipe_id, req.available)
        return recipe.to_dict()
    except RecipeError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


# --- Image Studio V1: Plan preview ---


@router.post("/studio/plan")
async def studio_plan(req: PlanPreviewRequest):
    """Preview a validated generation plan before committing.

    Returns the resolved plan with provenance so the user can inspect
    references and guidance before calling ``/studio/generate``.

    When *session_id* is supplied, the plan is persisted under a stable
    ``plan_id`` owned by that session, so ``/studio/generate`` can later
    dispatch from the approved plan instead of mutable form state.
    """
    from gateway.image_plan_types import ImagePlanError, build_image_plan

    if not req.prompt or not req.prompt.strip():
        raise HTTPException(status_code=400, detail="prompt must not be empty")

    try:
        plan = build_image_plan(
            req.prompt,
            character_id=req.character_id,
            recipe_id=req.recipe_id,
            guidance_tags=req.guidance_tags,
            content_lane=req.content_lane,
            consent_basis=req.consent_basis,
            adult_confirmed=req.adult_confirmed,
        )
    except ImagePlanError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    from gateway.image_guidance_bank import available_guidance_tags

    result = plan.to_dict()
    result["available_guidance_tags"] = available_guidance_tags()

    if req.session_id:
        from gateway.image_plan_store import PlanStoreError, persist_plan

        try:
            stored = persist_plan(req.session_id, plan)
        except PlanStoreError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        result["plan_id"] = stored.plan_id

    return result


# --- Image Studio: conversational sessions (issue #336, slice A5) ---


class SessionCreateRequest(BaseModel):
    title: Optional[str] = None
    project_id: Optional[int] = None
    character_id: Optional[str] = None
    reference_ids: Optional[List[str]] = None
    protected_traits: Optional[List[str]] = None


class SessionUpdateRequest(SessionCreateRequest):
    """PATCH body for an active session. Only supplied fields change."""

    clear_character: Optional[bool] = False


class AgentTurnRequest(BaseModel):
    """One natural-language turn for the bounded image-specialist controller."""

    session_id: str
    request: str
    recipe_id: Optional[str] = None


class AnchorRequest(BaseModel):
    job_id: str


def _session_payload(session) -> dict:
    """A session plus the turns and jobs a resumed conversation replays."""
    from gateway import image_sessions

    turns = image_sessions.list_turns(session.session_id)
    jobs = image_sessions.list_session_jobs(session.session_id)
    payload = session.to_dict()
    payload["turns"] = [t.to_dict() for t in turns]
    payload["jobs"] = [j.to_dict() for j in jobs]
    return payload


@router.post("/studio/sessions")
async def studio_create_session(req: SessionCreateRequest):
    from gateway.image_sessions import ImageSessionError, create_session

    try:
        session = create_session(
            title=req.title,
            project_id=req.project_id,
            character_id=req.character_id,
            reference_ids=req.reference_ids,
            protected_traits=req.protected_traits,
        )
    except ImageSessionError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _session_payload(session)


@router.get("/studio/sessions")
async def studio_list_sessions(limit: int = 50):
    from gateway.image_sessions import list_sessions

    return {"sessions": [s.to_dict() for s in list_sessions(limit=limit)]}


@router.get("/studio/sessions/{session_id}")
async def studio_get_session(session_id: str):
    """Resume: everything needed to rebuild the conversation after a restart."""
    from gateway.image_sessions import SessionNotFoundError, require_session

    try:
        session = require_session(session_id)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return _session_payload(session)


@router.patch("/studio/sessions/{session_id}")
async def studio_update_session(session_id: str, req: SessionUpdateRequest):
    """Bind or refresh a character/references on an active session.

    Only supplied fields change; the agent's session registry reads these on
    the next turn, so attaching a character here is how a reference image is
    wired into an already-open conversation.
    """
    from gateway.image_sessions import (
        ImageSessionError,
        SessionNotFoundError,
        update_session,
    )

    try:
        session = update_session(
            session_id,
            title=req.title,
            character_id=req.character_id,
            reference_ids=req.reference_ids,
            protected_traits=req.protected_traits,
            clear_character=req.clear_character,
        )
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ImageSessionError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _session_payload(session)


@router.post("/studio/sessions/{session_id}/anchor")
async def studio_set_anchor(session_id: str, req: AnchorRequest):
    """"Use this" — select a rendered result as the base for follow-up edits."""
    from gateway import undo_journal
    from gateway.image_sessions import (
        AnchorError,
        ImageSessionError,
        SessionNotFoundError,
        require_session,
    )

    try:
        journal_id = undo_journal.set_anchor_with_undo(session_id, req.job_id)
        session = require_session(session_id)
    except (SessionNotFoundError, undo_journal.UndoNotFound) as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except AnchorError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except ImageSessionError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    result = _session_payload(session)
    result["undo_journal_id"] = journal_id
    return result


@router.delete("/studio/sessions/{session_id}")
async def studio_end_session(session_id: str):
    from gateway.image_sessions import (
        ImageSessionError,
        SessionNotFoundError,
        end_session,
    )

    try:
        session = end_session(session_id)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ImageSessionError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return session.to_dict()


@router.post("/studio/agent")
async def studio_agent_turn(req: AgentTurnRequest):
    """Decide what one natural request means, without dispatching it.

    The controller returns a validated decision plus, for a render, the
    ``plan_id`` the caller passes to ``/studio/generate``. Splitting decision
    from dispatch is what lets the UI show what will change before any GPU
    starts billing.
    """
    from gateway.image_agent import (
        AgentLoopExhaustedError,
        AgentProtocolError,
        BudgetRefusedError,
        CapabilityError,
        ImageAgentError,
        UnknownReferenceError,
        UnsupportedOperationError,
        decide,
    )
    from gateway.image_sessions import SessionNotFoundError

    try:
        from gateway.routes.image_studio_jobs import _runtime_available_providers

        available_providers = await _runtime_available_providers()
        decision = decide(
            req.session_id, req.request, preferred_recipe=req.recipe_id,
            available_providers=available_providers,
        )
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except BudgetRefusedError as exc:
        raise HTTPException(status_code=429, detail=str(exc))
    except CapabilityError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except (UnknownReferenceError, UnsupportedOperationError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except (AgentProtocolError, AgentLoopExhaustedError) as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    except ImageAgentError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return decision.to_dict()


# --- Image Studio V1: Generate (Auto-routed) ---

@router.post("/studio/generate")
async def studio_generate(req: StudioGenerateRequest):
    from gateway import image_recipes
    from gateway.image_runner import (
        ImageDispatchNotSubmittedError,
        ImageRunnerError,
        estimated_cost_usd,
        paid_engine_available,
        read_anchor_artifact,
        run,
        run_edit,
    )

    # Dispatch from the stored approved plan when plan_id is supplied. The
    # plan owns the render inputs *and* the operation — request form fields
    # for prompt, character, recipe, and operation are ignored so a
    # post-approval edit cannot change what renders, and an approved edit
    # cannot be silently downgraded to a fresh generation.
    stored = None
    stored_intent: dict = {}
    operation = "txt2img"
    approved_edit_anchor: str | None = None
    character_ref_path: str | None = None
    if req.plan_id:
        from gateway.image_plan_store import (
            PlanNotApprovedError,
            PlanNotFoundError,
            PlanSessionMismatchError,
            PlanStoreError,
            require_approved_plan,
        )

        try:
            stored = require_approved_plan(req.plan_id, req.session_id or "")
        except PlanNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        except (PlanSessionMismatchError, PlanNotApprovedError, PlanStoreError) as exc:
            raise HTTPException(status_code=400, detail=str(exc))

        operation = stored.operation
        prompt = stored.refined_prompt
        stored_intent = getattr(stored, "intent", {}) or {}
        typed_cast = list(stored_intent.get("cast", []))
        if typed_cast:
            character_count = len(typed_cast)
            has_character = character_count > 0
        else:
            has_character = bool(stored.character_id)
            character_count = 1 if has_character else 0
        preferred_recipe = stored.recipe_id
        character_id = stored.character_id
        character_ref_path = getattr(stored, "character_ref_path", None)
        guidance_tags = stored.guidance_tags

        if operation == "img2img":
            # Fail loud before any spend or dispatch: a missing, unknown, or
            # non-owned anchor means this session cannot honestly edit that
            # image. Ownership reuses image_sessions' existing job-attachment
            # record rather than inventing a second ownership model.
            anchor_job_id = stored.anchor_job_id
            if not anchor_job_id:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"plan {stored.plan_id!r} is operation='img2img' but has "
                        "no anchor_job_id"
                    ),
                )
            from gateway import image_jobs as _image_jobs
            from gateway import image_sessions as _image_sessions

            if _image_jobs.get_job(anchor_job_id) is None:
                raise HTTPException(
                    status_code=400,
                    detail=f"anchor job {anchor_job_id!r} no longer exists",
                )
            owned_job_ids = {
                j.job_id
                for j in _image_sessions.list_session_jobs(stored.session_id)
            }
            if anchor_job_id not in owned_job_ids:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"anchor job {anchor_job_id!r} does not belong to "
                        f"session {stored.session_id!r}; refusing to edit an "
                        "image this session does not own"
                    ),
                )
            approved_edit_anchor = anchor_job_id

        # Content-lane contract (ADR 0040 #8): dispatch from the STORED plan's
        # policy, never from a request body. The approved plan is the only
        # trusted source of content_lane/consent_basis/adult_confirmed.
        content_lane = stored.content_lane
        consent_basis = stored.consent_basis
        adult_confirmed = stored.adult_confirmed
    else:
        if not req.prompt or not req.prompt.strip():
            raise HTTPException(status_code=400, detail="prompt must not be empty")

        prompt = req.prompt
        has_character = bool(req.character_id)
        character_count = 1 if has_character else 0
        preferred_recipe = req.recipe_id
        character_id = req.character_id
        guidance_tags = None
        if character_id:
            from gateway.image_characters import list_character_refs

            character_refs = list_character_refs(character_id)
            primary = next(
                (ref for ref in character_refs if ref.is_primary),
                character_refs[0] if character_refs else None,
            )
            character_ref_path = primary.storage_path if primary is not None else None

        # A plan-less /studio/generate call carries no trusted policy metadata:
        # it is safe lane, and a prompt can never promote itself to private.
        content_lane = "safe"
        consent_basis = None
        adult_confirmed = False

    # Resolve session context before routing, provider preflight, or spend. A
    # supplied session is authoritative for Project scope; an unknown session
    # must never be allowed to render first and fail only during attachment.
    dispatch_session_id = req.session_id or (stored.session_id if stored else None)
    session_context = None
    project_id: int | None = None
    if dispatch_session_id:
        from gateway.image_sessions import SessionNotFoundError, require_session

        try:
            session_context = require_session(dispatch_session_id)
        except SessionNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        project_id = session_context.project_id

    try:
        decision = image_recipes.auto_route(
            has_character=has_character,
            character_count=character_count,
            quality_tier=req.quality,
            identity_mode=req.identity,
            operation=operation,
            preferred_recipe=preferred_recipe,
        )
    except image_recipes.RecipeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    recipe = decision.recipe

    # Defense in depth for typed multi-character plans. Even if routing is
    # forced or replaced by a test/operator hook, no renderer may receive a
    # cast larger than the recipe explicitly supports.
    if character_count > 1:
        max_characters = int(getattr(recipe, "max_characters", 0) or 0) if recipe else 0
        if (
            recipe is None
            or not getattr(recipe, "supports_characters", False)
            or max_characters < character_count
        ):
            raise HTTPException(
                status_code=503,
                detail=(
                    f"recipe {decision.recipe_id!r} supports at most "
                    f"{max_characters} character(s), but the approved plan requires "
                    f"{character_count}"
                ),
            )

    # auto_route does not filter on operation, so the img2img capability has
    # to be asserted here or an approved edit would route to a text-only
    # recipe (mirrors image_agent._route_recipe's same assertion).
    if operation == "img2img" and (recipe is None or not recipe.supports_img2img):
        raise HTTPException(
            status_code=503,
            detail=(
                f"recipe {decision.recipe_id!r} does not support img2img; "
                "no available recipe can perform a reference-conditioned edit"
            ),
        )

    # Content-lane seam (ADR 0040 #8): select the execution target from the
    # stored plan's policy BEFORE any cost estimate or availability preflight.
    # Private work must pick a private executor first so a hosted availability
    # gate or hosted spend reservation can never run for private work — even if
    # the recipe metadata names a hosted provider.
    from gateway.image_policy import (
        ImagePolicyError,
        validate_image_execution_policy,
    )

    if content_lane == "private_adult":
        # v1's only Kitty-controlled private executor is the worker edit lane
        # (run_edit → kitty_worker). A private text-to-image plan has no
        # private executor yet, so it is refused here — never downgraded to a
        # hosted engine.
        if operation != "img2img":
            raise HTTPException(
                status_code=400,
                detail=(
                    "content_lane='private_adult' has no private text-to-image "
                    "executor in v1; only the worker edit lane (img2img) is "
                    "private, refusing to route private work to a hosted provider"
                ),
            )
        execution_target = "kitty_worker"
    else:
        execution_target = recipe.provider if recipe else "comfyui"

    try:
        validate_image_execution_policy(
            content_lane, consent_basis, adult_confirmed, execution_target
        )
    except ImagePolicyError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    engine = execution_target

    # Hosted FLUX.2 (BFL Direct) selection (IL-03/IL-04). For provider=="flux2"
    # the recipe names an explicit flux2 execution target; the exact model,
    # estimate, availability, and dispatch must all agree on that one target.
    flux2_target = None
    compiled_request = None
    reference_bytes: tuple[bytes, ...] = ()
    render_width = 1024
    render_height = 1024

    if engine == "flux2":
        from gateway.flux2_compiler import (
            CompiledReference,
            Flux2CompilerError,
            compile_flux2_request,
        )
        from gateway.flux2_targets import (
            Flux2TargetError,
            resolve_flux2_target,
        )

        if not recipe or not recipe.execution_target:
            raise HTTPException(
                status_code=400,
                detail="recipe for the hosted FLUX.2 lane names no execution target",
            )
        try:
            flux2_target = resolve_flux2_target(recipe.execution_target)
        except Flux2TargetError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

        if recipe.default_width and recipe.default_width > 0:
            render_width = recipe.default_width
        if recipe.default_height and recipe.default_height > 0:
            render_height = recipe.default_height

        refs: list[CompiledReference] = []
        ref_blobs: list[bytes] = []
        if operation == "img2img":
            if approved_edit_anchor is None:
                raise HTTPException(
                    status_code=500,
                    detail="approved img2img plan lost its validated anchor before dispatch",
                )
            try:
                anchor_bytes, anchor_name = read_anchor_artifact(
                    approved_edit_anchor
                )
            except ImageRunnerError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            refs.append(
                CompiledReference(
                    reference_id=approved_edit_anchor,
                    role="anchor",
                    order=1,
                    name=anchor_name,
                )
            )
            ref_blobs.append(anchor_bytes)
        stored_provenance = list(stored.references if stored else [])
        typed_bindings = list(stored_intent.get("references", []))
        if typed_bindings:
            # Role-aware reference selection (ADR 0040): validate every bound
            # reference against the selected recipe's declared capabilities and
            # order identity references by cast depth before dispatch. A
            # capability the provider cannot carry fails loudly rather than
            # silently dropping or mis-using the reference.
            from gateway.image_reference_selector import (
                ReferenceCapabilityError,
                UnknownReferenceRoleError,
                select_references,
            )

            try:
                selected = select_references(
                    typed_bindings,
                    list(stored_intent.get("cast", [])),
                    recipe=recipe,
                    operation=operation,
                )
            except (UnknownReferenceRoleError, ReferenceCapabilityError) as exc:
                raise HTTPException(status_code=400, detail=str(exc))
            provenance_by_id = {
                str(prov.get("reference_id")): prov
                for prov in stored_provenance
                if isinstance(prov, dict) and prov.get("reference_id")
            }
            for binding in selected:
                reference_id = binding.reference_id
                prov = provenance_by_id.get(reference_id)
                if prov is None:
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            f"approved plan reference {reference_id!r} has no durable "
                            "reference provenance"
                        ),
                    )
                path = prov.get("path")
                if not path or not Path(path).is_file():
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            f"approved plan reference {reference_id!r} is missing "
                            "from local storage"
                        ),
                    )
                refs.append(
                    CompiledReference(
                        reference_id=reference_id,
                        role=binding.role,
                        order=len(refs) + 1,
                        name=prov.get("name"),
                        cast_slot=binding.cast_slot,
                        character_id=binding.character_id,
                        position=binding.position,
                        depth_order=binding.depth_order,
                    )
                )
                ref_blobs.append(Path(path).read_bytes())
        else:
            # Legacy persisted plans predate typed reference bindings. Preserve
            # their old projection so historical approved plans remain usable.
            for prov in stored_provenance:
                path = prov.get("path") if isinstance(prov, dict) else getattr(prov, "path", None)
                if not path or not Path(path).is_file():
                    continue
                refs.append(
                    CompiledReference(
                        reference_id=str(path),
                        role="identity",
                        order=len(refs) + 1,
                        name=(prov.get("name") if isinstance(prov, dict) else getattr(prov, "name", None)),
                    )
                )
                ref_blobs.append(Path(path).read_bytes())
        reference_bytes = tuple(ref_blobs)

        protected: list[str] = []
        requested: list[str] = []
        if stored is not None:
            protected = list(stored.intent.get("protected_traits", []))
            requested = list(stored.intent.get("requested_changes", []))
        elif session_context is not None:
            protected = list(session_context.protected_traits or [])
            requested = list(session_context.requested_changes or [])
        try:
            compiled_request = compile_flux2_request(
                prompt,
                references=refs,
                operation=operation,
                # StudioGenerateRequest intentionally has no user-authored seed.
                # Seeds become approved batch/VariationStrategy state in IL-08;
                # do not invent mutable request-side reproducibility here.
                seed=None,
                width=render_width,
                height=render_height,
                quality_tier=req.quality,
                protected_traits=protected,
                requested_changes=requested,
                negative_prompt=req.negative_prompt,
            )
        except Flux2CompilerError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        reference_limit = getattr(flux2_target, "reference_limit", None)
        if reference_limit is not None and len(refs) > int(reference_limit):
            target_name = getattr(
                flux2_target, "target_id", getattr(flux2_target, "model_id", "flux2")
            )
            raise HTTPException(
                status_code=400,
                detail=(
                    f"FLUX.2 target {target_name!r} allows at most "
                    f"{reference_limit} references; compiled {len(refs)}"
                ),
            )
        try:
            estimated_cost = flux2_target.estimate_cost_usd(
                render_width, render_height, operation
            )
        except (Flux2TargetError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    else:
        try:
            estimated_cost = estimated_cost_usd(engine)
        except ImageRunnerError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    paid_attempt_reserved = False
    paid_reservation_id: str | None = None
    if estimated_cost > 0:
        if not req.session_id:
            raise HTTPException(
                status_code=400,
                detail="paid image generation requires a session so spend can be budgeted",
            )
        available, reason = paid_engine_available(engine)
        if not available:
            raise HTTPException(status_code=400, detail=reason)

        from gateway.image_agent import AgentBudget
        from gateway.image_sessions import (
            ImageSessionError,
            SessionBudgetExceededError,
            reserve_attempt,
        )

        budget = AgentBudget()
        try:
            reservation = reserve_attempt(
                req.session_id,
                cost_usd=estimated_cost,
                max_attempts=budget.max_attempts,
                max_spend_usd=budget.max_spend_usd,
            )
            paid_attempt_reserved = True
            paid_reservation_id = reservation.reservation_id
        except SessionBudgetExceededError as exc:
            raise HTTPException(status_code=429, detail=str(exc))
        except ImageSessionError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    job_plan_id = stored.plan_id if stored is not None else None
    stored_intent_for_job = (
        getattr(stored, "intent", None) if stored is not None else None
    )
    job_intent_json = (
        json.dumps(stored_intent_for_job, sort_keys=True, separators=(",", ":"))
        if stored_intent_for_job
        else None
    )

    try:
        if engine == "flux2":
            result = await run(
                engine,
                prompt,
                recipe=recipe,
                character_id=character_id,
                character_ref_path=character_ref_path,
                negative_prompt=req.negative_prompt,
                guidance_tags=guidance_tags,
                content_lane=content_lane,
                consent_basis=consent_basis,
                adult_confirmed=adult_confirmed,
                flux2_target=flux2_target,
                compiled_request=compiled_request,
                reference_bytes=reference_bytes,
                project_id=project_id,
                plan_id=job_plan_id,
                intent_json=job_intent_json,
                session_id=req.session_id if paid_attempt_reserved else None,
                reserved_cost_usd=estimated_cost if paid_attempt_reserved else None,
                reservation_id=paid_reservation_id,
                quality_tier=req.quality,
            )
        elif operation == "img2img":
            if approved_edit_anchor is None:
                raise HTTPException(
                    status_code=500,
                    detail="approved img2img plan lost its validated anchor before dispatch",
                )
            # Safe hosted recipes that explicitly support image input must execute
            # through their approved provider. Private-adult edits remain pinned to
            # run_edit()/kitty_worker by the policy-derived execution_target above.
            if content_lane == "safe" and engine in {"openai", "openrouter", "flux", "drawthings"}:
                try:
                    source_image, _source_name = read_anchor_artifact(approved_edit_anchor)
                except ImageRunnerError as exc:
                    raise HTTPException(status_code=400, detail=str(exc)) from exc
                result = await run(
                    engine,
                    prompt,
                    recipe=recipe,
                    character_id=character_id,
                    character_ref_path=character_ref_path,
                    negative_prompt=req.negative_prompt,
                    parent_id=approved_edit_anchor,
                    source_image=source_image,
                    content_lane=content_lane,
                    consent_basis=consent_basis,
                    adult_confirmed=adult_confirmed,
                    project_id=project_id,
                    plan_id=job_plan_id,
                    intent_json=job_intent_json,
                    session_id=req.session_id if paid_attempt_reserved else None,
                    reserved_cost_usd=estimated_cost if paid_attempt_reserved else None,
                reservation_id=paid_reservation_id,
                    quality_tier=req.quality,
                )
            else:
                result = await run_edit(
                    prompt,
                    anchor_job_id=approved_edit_anchor,
                    recipe=recipe,
                    negative_prompt=req.negative_prompt,
                    content_lane=content_lane,
                    consent_basis=consent_basis,
                    adult_confirmed=adult_confirmed,
                    project_id=project_id,
                    plan_id=job_plan_id,
                    intent_json=job_intent_json,
                )
        else:
            result = await run(
                engine,
                prompt,
                recipe=recipe,
                character_id=character_id,
                character_ref_path=character_ref_path,
                negative_prompt=req.negative_prompt,
                guidance_tags=guidance_tags,
                content_lane=content_lane,
                consent_basis=consent_basis,
                adult_confirmed=adult_confirmed,
                project_id=project_id,
                plan_id=job_plan_id,
                intent_json=job_intent_json,
                session_id=req.session_id if paid_attempt_reserved else None,
                reserved_cost_usd=estimated_cost if paid_attempt_reserved else None,
                reservation_id=paid_reservation_id,
            )
        # Bind the render back to its conversation so a restart can replay it
        # and "use this" has something to anchor on. A failure to bind is
        # surfaced, not swallowed: a job the session cannot see is a job the
        # user cannot select.
        if req.session_id:
            from gateway.image_sessions import (
                ImageSessionError,
                attach_job,
                reconcile_reserved_attempt_cost,
                record_attempt,
            )

            try:
                if (
                    paid_attempt_reserved
                    and paid_reservation_id is not None
                    and result.cost_usd is not None
                ):
                    reconcile_reserved_attempt_cost(
                        req.session_id,
                        reservation_id=paid_reservation_id,
                        actual_cost_usd=result.cost_usd,
                    )
                attach_job(req.session_id, result.job_id)
                if not paid_attempt_reserved:
                    record_attempt(req.session_id)
            except ImageSessionError as exc:
                raise HTTPException(status_code=400, detail=str(exc))
        return {
            "job_id": result.job_id,
            "filename": result.filename,
            "actual_cost_usd": result.cost_usd,
            "actual_cost_source": getattr(result, "cost_source", None),
            "recipe": result.recipe,
            "routing_reason": decision.reason,
            "plan_id": req.plan_id,
            "session_id": req.session_id,
        }
    except ImageDispatchNotSubmittedError as e:
        if paid_attempt_reserved and req.session_id and paid_reservation_id is not None:
            from gateway.image_sessions import (
                ImageSessionError,
                release_reserved_attempt_cost,
            )

            try:
                release_reserved_attempt_cost(
                    req.session_id, reservation_id=paid_reservation_id
                )
            except ImageSessionError as release_exc:
                raise HTTPException(status_code=500, detail=str(release_exc)) from release_exc
        status = 503 if "not running" in str(e).lower() else 400
        raise HTTPException(status_code=status, detail=str(e))
    except ImageRunnerError as e:
        status = 503 if "not running" in str(e).lower() else 400
        raise HTTPException(status_code=status, detail=str(e))
    except TimeoutError as exc:
        raise HTTPException(status_code=504, detail=str(exc))
    except HTTPException:
        # A status this handler already chose must reach the client intact.
        # Without this the generic clause below rewraps it as a 500 whose body
        # is the text of the original error, hiding the real cause.
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
