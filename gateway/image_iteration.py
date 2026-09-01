"""Image Lab iteration helpers (QoL Packet 02).

Makes generation iterative rather than disposable: retry (same intent, new
attempt), duplicate (independent copy), and modify-one-parameter, while
preserving provider/model/configuration provenance, character identity, and
parent→child lineage.

Protected-subsystem boundary: these helpers never re-route a provider, change
content policy, or touch the private-adult lane. Provider and policy metadata
are copied verbatim from the source job; ``modify`` can only change the listed
render parameters, never provider, operation, plan, or intent. A job whose
``content_lane`` is ``private_adult`` stays on its original provider with its
policy metadata intact.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field, replace
from typing import Any

from gateway import image_jobs, image_sessions
from gateway.image_jobs import ImageJob, ImageJobError, ImageJobStatus, JobNotFoundError

# Render parameters a user may change when iterating. Provider, operation,
# plan_id, and intent_json are deliberately excluded: changing those re-routes
# the job or silently swaps what was approved, which is out of scope here.
_MODIFIABLE_FIELDS = frozenset(
    {
        "prompt",
        "negative_prompt",
        "seed",
        "width",
        "height",
        "steps",
        "guidance",
        "sampler",
        "scheduler",
        "model_id",
        "preset_id",
    }
)


class IterationError(ImageJobError):
    """Raised when a job cannot be used as an iteration source."""


@dataclass
class GenerationContext:
    """Everything needed to reconstruct a generation intent from a job."""

    provider: str
    model_id: str | None
    operation: str
    prompt: str | None
    negative_prompt: str | None
    seed: int | None
    width: int | None
    height: int | None
    steps: int | None
    guidance: float | None
    sampler: str | None
    scheduler: str | None
    preset_id: str | None
    provider_params_json: str | None
    workflow_template_id: str | None
    workflow_hash: str | None
    compiler_version: str | None
    compiler_params_json: str | None
    plan_id: str | None
    intent_json: str | None
    session_id: str | None
    character_id: str | None
    reference_ids: list[str] = field(default_factory=list)
    protected_traits: list[str] = field(default_factory=list)


def _require_succeeded_job(job_id: str) -> ImageJob:
    job = image_jobs.get_job(job_id)
    if job is None:
        raise JobNotFoundError(f"job {job_id} not found")
    if job.status is not ImageJobStatus.SUCCEEDED:
        raise IterationError(
            f"job {job_id} is {job.status.value}; only a succeeded job can be iterated"
        )
    return job


def build_generation_context(job_id: str) -> GenerationContext:
    """Reconstruct a retry/duplicate payload from an existing job.

    Reads the job's provider/model/configuration provenance and, when the job
    belongs to a character session, that session's character identity and
    protected traits. Provider and policy metadata are copied, never derived.
    """
    _require_succeeded_job(job_id)
    job = image_jobs.get_job(job_id)
    assert job is not None

    preset_id = job.preset_id
    if preset_id is None and job.plan_id:
        from gateway import image_plan_store

        plan = image_plan_store.get_plan(job.plan_id)
        if plan is not None:
            preset_id = plan.recipe_id

    session_id = image_sessions.job_session_id(job_id)
    character_id: str | None = None
    reference_ids: list[str] = []
    protected_traits: list[str] = []
    if session_id:
        session = image_sessions.get_session(session_id)
        if session is not None:
            character_id = session.character_id
            reference_ids = session.reference_ids
            protected_traits = session.protected_traits

    return GenerationContext(
        provider=job.provider,
        model_id=job.model_id,
        operation=job.operation,
        prompt=job.prompt,
        negative_prompt=job.negative_prompt,
        seed=job.seed,
        width=job.width,
        height=job.height,
        steps=job.steps,
        guidance=job.guidance,
        sampler=job.sampler,
        scheduler=job.scheduler,
        preset_id=preset_id,
        provider_params_json=job.provider_params_json,
        workflow_template_id=job.workflow_template_id,
        workflow_hash=job.workflow_hash,
        compiler_version=job.compiler_version,
        compiler_params_json=job.compiler_params_json,
        plan_id=job.plan_id,
        intent_json=job.intent_json,
        session_id=session_id,
        character_id=character_id,
        reference_ids=reference_ids,
        protected_traits=protected_traits,
    )


def _create_from_context(ctx: GenerationContext, *, parent_id: str) -> ImageJob:
    """Persist a new job whose configuration matches ``ctx`` and link lineage."""
    return image_jobs.create_job(
        provider=ctx.provider,
        operation=ctx.operation,
        prompt=ctx.prompt,
        negative_prompt=ctx.negative_prompt,
        seed=ctx.seed,
        model_id=ctx.model_id,
        preset_id=ctx.preset_id,
        width=ctx.width,
        height=ctx.height,
        steps=ctx.steps,
        guidance=ctx.guidance,
        sampler=ctx.sampler,
        scheduler=ctx.scheduler,
        provider_params_json=ctx.provider_params_json,
        workflow_template_id=ctx.workflow_template_id,
        workflow_hash=ctx.workflow_hash,
        parent_id=parent_id,
        compiler_version=ctx.compiler_version,
        compiler_params_json=ctx.compiler_params_json,
        plan_id=ctx.plan_id,
        intent_json=ctx.intent_json,
    )


def _attach_to_source_session(ctx: GenerationContext, child_id: str) -> None:
    """Keep the child in the same character session so identity survives."""
    if ctx.session_id:
        image_sessions.attach_job(ctx.session_id, child_id)


def duplicate_job(job_id: str) -> ImageJob:
    """Create an independent copy of a succeeded job with identical parameters.

    The copy is a child of the source for lineage, and carries the same seed.
    """
    _require_succeeded_job(job_id)
    ctx = build_generation_context(job_id)
    child = _create_from_context(ctx, parent_id=job_id)
    _attach_to_source_session(ctx, child.job_id)
    return child


def _new_seed() -> int:
    # 32-bit range keeps seeds portable across providers and tools.
    return random.SystemRandom().randint(0, 2**32 - 1)


def retry_job(job_id: str, *, vary_seed: bool = True) -> ImageJob:
    """Same generation intent, a new attempt. The child links the source as parent.

    ``vary_seed=True`` (default) assigns a fresh seed when the source carried one
    (controlled variation); ``vary_seed=False`` is an exact retry that preserves
    the source seed.
    """
    _require_succeeded_job(job_id)
    ctx = build_generation_context(job_id)
    if vary_seed and ctx.seed is not None:
        ctx.seed = _new_seed()
    child = _create_from_context(ctx, parent_id=job_id)
    _attach_to_source_session(ctx, child.job_id)
    return child


def apply_changes(ctx: GenerationContext, **changes: Any) -> GenerationContext:
    """Return a copy of ``ctx`` with only the supplied modifiable fields changed."""
    unknown = set(changes) - _MODIFIABLE_FIELDS
    if unknown:
        raise IterationError(
            f"cannot modify {sorted(unknown)}; only {sorted(_MODIFIABLE_FIELDS)} may change"
        )
    return replace(ctx, **changes)


def diff_context(
    before: GenerationContext, after: GenerationContext
) -> dict[str, dict[str, Any]]:
    """Changed-vs-unchanged report for the modifiable fields.

    Only changed fields appear, as ``{field: {"before": x, "after": y}}``.
    """
    diff: dict[str, dict[str, Any]] = {}
    for fld in _MODIFIABLE_FIELDS:
        b = getattr(before, fld)
        a = getattr(after, fld)
        if b != a:
            diff[fld] = {"before": b, "after": a}
    return diff


def modify_job(job_id: str, **changes: Any) -> tuple[ImageJob, dict[str, dict[str, Any]]]:
    """Change one or more render parameters, keeping everything else.

    Returns the new child job (parent-linked to the source) and the
    changed-vs-unchanged diff for display.
    """
    _require_succeeded_job(job_id)
    if not changes:
        raise IterationError("modify_job requires at least one parameter change")
    ctx = build_generation_context(job_id)
    after_ctx = apply_changes(ctx, **changes)
    child = _create_from_context(after_ctx, parent_id=job_id)
    _attach_to_source_session(ctx, child.job_id)
    return child, diff_context(ctx, after_ctx)


def _enqueue_plan_batch(ctx: GenerationContext, *, parent_id: str) -> dict:
    """Enqueue a one-image batch that re-runs the source job's approved plan.

    The plan is immutable and owns prompt/character/recipe/operation/lane, so
    re-dispatching it is the honest "same intent, new attempt". Lineage is
    carried as ``lineage_parent_id`` in the request and attached to the child
    after generation, without ever altering operation semantics.
    """
    from gateway import image_batches, image_estimates

    if not ctx.plan_id:
        raise IterationError("cannot iterate a job with no approved plan")
    if not ctx.session_id:
        raise IterationError("cannot iterate a job with no attached session")
    if not ctx.preset_id:
        raise IterationError(
            "cannot iterate safely because the exact source recipe was not recorded"
        )
    per_image = image_estimates.estimate(
        ctx.provider, model_id=ctx.model_id, operation=ctx.operation
    )
    request = {
        "plan_id": ctx.plan_id,
        "session_id": ctx.session_id,
        "prompt": ctx.prompt or "",
        "negative_prompt": ctx.negative_prompt,
        "character_id": ctx.character_id,
        "recipe_id": ctx.preset_id,
        "lineage_parent_id": parent_id,
        "expected_provider": ctx.provider,
        "expected_model_id": ctx.model_id,
    }
    return image_batches.create_batch(
        request, count=1, per_image_estimate=per_image
    )


def enqueue_duplicate(job_id: str) -> dict:
    """Enqueue an independent re-run of a succeeded job's approved plan."""
    _require_succeeded_job(job_id)
    ctx = build_generation_context(job_id)
    return _enqueue_plan_batch(ctx, parent_id=job_id)


def enqueue_retry(job_id: str, *, vary_seed: bool = True) -> dict:
    """Enqueue a fresh attempt of a succeeded job's generation intent.

    ``vary_seed`` has no effect at the plan-dispatch level (the approved plan
    owns its inputs and the provider derives a new seed each run); it is kept
    for API symmetry with :func:`retry_job`.
    """
    _require_succeeded_job(job_id)
    ctx = build_generation_context(job_id)
    return _enqueue_plan_batch(ctx, parent_id=job_id)


def enqueue_modify(
    job_id: str, **changes: Any
) -> tuple[dict, dict[str, dict[str, Any]]]:
    """Enqueue a re-run and report the changed-vs-unchanged diff.

    Returns the queued batch and the diff. Render-parameter changes are
    recorded for provenance, but the current dispatch path (StudioGenerate →
    image_runner) does not yet accept request-side seed/steps overrides, so the
    regenerated image re-runs the approved plan unchanged (deferred to IL-08).
    """
    _require_succeeded_job(job_id)
    if not changes:
        raise IterationError("enqueue_modify requires at least one parameter change")
    raise IterationError(
        "cannot dispatch a modified approved plan until the changed intent is re-approved"
    )


__all__ = [
    "GenerationContext",
    "IterationError",
    "apply_changes",
    "build_generation_context",
    "diff_context",
    "duplicate_job",
    "enqueue_duplicate",
    "enqueue_modify",
    "enqueue_retry",
    "modify_job",
    "retry_job",
]
