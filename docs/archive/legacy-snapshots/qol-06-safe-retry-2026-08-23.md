# QoL-06 — Unified Safe Retry
> **Historical snapshot archived 2026-09-03 — not current instruction.** Original status, commands, branch names, provider details, and next-step language below are preserved as dated evidence only. Use `docs/ROADMAP.md`, `docs/ACTIVE_MISSION.md`, current ADRs, and live runtime/Git evidence for present work.


**Status:** Active (implementation)
**Authorized by:** docs/quality_of_life_packets.md §06; interactive lane, lease 2026-08-23T22:00:00-06:00
**Scope:** Automation retry (execution semantics) + Image retry (durable lineage) — no Builder governance, no image-policy changes

## Objective

Make retrying an operation predictable: a retry preserves the original execution
intent while receiving a new execution identity. This covers both Automation
runs and Image Lab jobs, and re-evaluates authority on every retry.

## Constraints

- Use the existing #550 Automation Run ledger and existing image_jobs store.
  No new database, workflow engine, or parallel explanation store.
- Retry must never reuse a stale authorization: route the retried dispatch
  through the same code path that re-evaluates `action_grants` (the security
  rule). A revoked or expired grant must produce a truthful refusal on the
  retry run, not a silent pass.
- "Retry" means predictable repetition of the same intent. The retry must not
  silently run a different action or different parameters than the original.
- Image Lab is a protected subsystem: no changes to image policy, provider
  eligibility, private/adult routing, character identity, or moderation.
  Private-adult generation continues through the existing approved lane.
- No fake run/evidence rows for things that genuinely never executed.

## Design

### Automation retry (gateway/automation_runs.py + gateway/routes/automations.py)

1. Migration `049_automation_runs_payload.sql`: `ALTER TABLE automation_runs ADD COLUMN payload_json TEXT;`
2. `begin_run(..., payload=None)`: persists `payload_json` so the ledger keeps
   the parameters that produced the run (currently dropped).
3. `retry_run(run_id, *, started_at=None) -> dict`: requires the original run
   to exist and NOT be `running`; inserts a NEW `running` row with a fresh
   `arun_<uuid>` id reusing `automation_id`, `action`, `trigger_kind`,
   `trigger_ref`, `schedule_id`, `due_at`, and `payload_json` from the original.
   New timestamps, new run identity. Reads the original's `policy_json`
   evidence to recover the policy scope (`scope_type`/`scope_id`) so the retry
   re-evaluates at the same scope.
4. Route `POST /automations/runs/{run_id}/retry`: 404 when the run is missing,
   409 when still running; otherwise `retry_run` then re-dispatch through
   `automation_actions.run_action(action, trigger_kind=..., automation_id=...,
   trigger_ref=..., schedule_id=..., payload=stored_payload,
   run_id=new_run_id, policy_scope_type=..., policy_scope_id=...)`. Because
   `run_action` calls `_policy_evidence` → `action_grants.evaluate` fresh on
   every dispatch, the retry re-evaluates authority: a revoked/expired grant
   produces `policy_refused` with a NEW run id and NEW evidence, while an
   intact grant executes with the ORIGINAL payload.

### Image retry (gateway/image_jobs.py + gateway/routes/extended.py)

1. `retry_job(job_id) -> ImageJob`: requires the original job to be terminal
   (any terminal state) and FAILED retries not exhausted; creates a NEW child
   job via `create_job` copying `provider`, `operation`, `prompt`,
   `negative_prompt`, `seed`, `model_id`, `preset_id`, `width`, `height`,
   `steps`, `guidance`, `sampler`, `scheduler`, `provider_params_json`,
   `workflow_template_id`, `workflow_hash`, `compiler_version`,
   `compiler_params_json`, `plan_id`, `intent_json`, `max_retries`, with
   `parent_id=original job_id` (lineage) and `priority` inherited. New job id,
   new timestamps, status `created`.
   - Content lane and character identity survive because `plan_id` +
     `intent_json` are copied verbatim; the plan owns the lane and character
     casting and is never re-derived from the request.
2. Route `POST /image/jobs/{job_id}/retry`: 404 when missing; 409 when not
   terminal; otherwise creates the child job and returns it. The child is
   picked up by the existing dispatch path (batch worker / queue). No provider
   routing or policy logic changes.

### UI (gateway/kitty-chat/src/components/)

- Automations runs view: a "retry" affordance on terminal run rows that calls
  the retry route and refetches the runs list.
- Image Gallery / Studio: a "retry" affordance on terminal (failed) job rows
  that calls the image retry route, then invalidates the gallery query.
- Both show the resulting new run/job id and keep existing surface patterns
  (SectionCard, actionButtonStyle, StatusBadge).

## First deliverable

RED tests for the automation retry matrix, then `retry_run` + route + migration.

## Acceptance

- Successful retry creates a new run id + new timestamps + new evidence.
- Failed retry records the failure on the new run, original untouched.
- Revoked grant before retry → `policy_refused` on the new run (security rule).
- Changed action identity / changed parameters are refused or preserved —
  never silently different execution.
- Image retry preserves character (plan_id/intent), private lane, provider,
  settings, and lineage (`parent_id`); `list_children` shows the child.

## Deferred

Builder execution retry; Explainable Memory (#04); Safe Self-Recovery (#05).
