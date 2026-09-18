# Salvage 02 — governed prompt experiments without a second learning authority

## Decision

**Keep the useful closed-loop experiment idea; discard the historical self-modifying prompt database.**

Historical source:

`git -C "/Users/jacobbrizinnski/Projects (from backup)/kitty" show '6a7900a^:src/utils/meta_prompt_optimizer.py'`

The May implementation had several good product ideas:

- identify recurring friction;
- propose an explicit prompt delta;
- show a diff;
- version the candidate;
- measure post-change satisfaction;
- roll back when results worsen.

Its storage and automatic behavior should not return.

## Current authority already solves the hard part

Current Kitty has a stronger learning boundary:

- `scripts/session_learning.py` records structured evidence.
- ordinary problems require recurrence before promotion;
- integrity/security/data-loss/cost failures may promote immediately;
- promotion is evidence, **not implementation authority**;
- `compare_capability_runs()` enforces matched task sets and records paired evaluation context;
- ADR 0025 explicitly forbids a second backlog/control plane and hidden promotion.

Therefore prompt experiments should be a consumer of current learning evidence, never a replacement.

## Modern experiment lifecycle

### 1. Qualify the problem

Input must be one of:

- a promoted workflow signal; or
- a deliberately requested prompt experiment with explicit owner/scope.

A single vague annoyance does not silently mutate instructions.

### 2. Bind baseline exactly

Identify the actual prompt-bearing artifact:

- repository path;
- component/section;
- baseline Git SHA;
- baseline content hash.

If the effective prompt is assembled from several sources, bind every relevant source hash. Do not create a synthetic “active prompt” row that can disagree with Git.

### 3. Produce a candidate diff

The experiment artifact is a normal patch/diff against the prompt-bearing source.

Required metadata:

- signal/task identity;
- hypothesis;
- intended behavior change;
- non-goals;
- baseline SHA/hash;
- candidate SHA/hash;
- evaluation task set;
- scorer/version;
- rollback target.

The human-readable diff is the review surface.

### 4. Evaluate baseline and candidate on matched tasks

Reuse the existing paired-evaluation contract in `scripts/session_learning.py`.

The baseline and candidate must use:

- identical task keys;
- the same model;
- the same workspace/input fixtures;
- the same scorer;
- pinned settings where material.

Measure outcome quality, not verbosity alone.

For user-experience changes, explicit human preference evidence may supplement objective checks; see `04-human-preference-evidence.md`.

### 5. Keep activation under existing authority

A successful experiment does **not** modify live prompt state itself.

Promotion uses the normal owner:

- Git/PR for repository prompts;
- the existing governed config path for runtime configuration;
- Builder only when an approved packet owns the implementation.

No background optimizer may update `AGENTS.md`, `SOUL.md`, skills, routing or system prompts on its own.

### 6. Rollback using the existing source of truth

Rollback is the exact previous Git/config version, not a private SQLite pointer.

A rollback receipt should name:

- failed candidate SHA/hash;
- restored baseline SHA/hash;
- evidence that triggered rollback;
- whether the candidate remains useful as research evidence.

## Satisfaction evidence

The old optimizer used a floating-point satisfaction table and an arbitrary threshold after three samples. Do not copy that literally.

Prefer evidence with provenance:

- explicit chosen-vs-rejected human comparison;
- correction/redirect signal tied to the candidate;
- acceptance-test regression;
- matched task score degradation;
- repeated workflow signal.

Unknown stays unknown. Absence of complaint is not satisfaction.

## Suggested schema for an experiment receipt

This is a **receipt shape**, not a new database:

```json
{
  "experiment_id": "prompt-exp-...",
  "signal_key": "optional-existing-workflow-signal",
  "component": "path-or-component",
  "baseline": {
    "git_sha": "...",
    "content_sha256": "..."
  },
  "candidate": {
    "git_sha": "...",
    "content_sha256": "..."
  },
  "hypothesis": "...",
  "paired_eval": {
    "task_keys": ["..."],
    "model": "...",
    "workspace": "...",
    "scorer": "...",
    "baseline_mean": null,
    "candidate_mean": null
  },
  "human_preferences": [],
  "decision": "keep|rollback|inconclusive",
  "decision_evidence": ["..."]
}
```

Store the receipt only in an existing evidence location appropriate to the owning workflow.

## What not to recover

Do not recreate historical tables such as:

- `prompt_versions`
- `active_prompts`
- `friction_events`
- `satisfaction_metrics`

unless a future architecture decision proves Git/current evidence cannot represent the necessary state.

Do not use simplistic phrase matching such as “tl;dr” or “wrong” as sufficient authority to rewrite prompts. Those may be weak signals, nothing more.

## Acceptance for a future implementation

A prompt experiment feature is acceptable only if it proves all of the following:

1. no candidate can activate itself;
2. baseline/candidate are exact-hash bound;
3. evaluation task sets are matched;
4. a failed or unavailable evaluator cannot become approval;
5. rollback restores an exact previous version;
6. existing learning/roadmap/Builder authority remains canonical;
7. the feature can be removed without losing product execution state.
