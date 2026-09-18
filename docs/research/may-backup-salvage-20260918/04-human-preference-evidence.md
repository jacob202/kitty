# Salvage 04 — human preference evidence

## Decision

**Adapt the historical chosen-vs-rejected record as bounded evaluation evidence. Do not revive “RLHF collection” as a training subsystem.**

Historical source:

`git -C "/Users/jacobbrizinnski/Projects (from backup)/kitty" show 'ba10080^:src/eval/rlhf_collection.py'`

The useful primitive was simple:

- exact task/query;
- several candidate responses;
- explicit chosen response;
- rejected response(s);
- session and metadata.

Current Kitty already has stronger numeric paired evaluation in `scripts/session_learning.py`, including matched task keys and fixed model/workspace/scorer context. What appears to be missing is a small **human comparison receipt** for cases where subjective preference is itself the ground truth.

## Appropriate uses

Good uses:

- A/B prompt experiments;
- Image Lab identity/style comparisons;
- UI wording alternatives;
- answer-format preferences;
- model comparison on the same task;
- explicit “this version is better than that one” feedback.

Bad uses:

- inferring preferences from silence;
- silently learning from every click;
- changing routing automatically;
- treating one preference as a durable universal rule;
- storing sensitive full conversations when hashes/references suffice.

## Proposed receipt shape

```json
{
  "schema_version": 1,
  "preference_id": "pref-...",
  "task_key": "stable-matched-task-key",
  "observed_at": "...",
  "source": "explicit_human_choice",
  "context": {
    "workspace": "...",
    "model_or_engine": "...",
    "scorer_version": "optional"
  },
  "option_a": {
    "artifact_ref": "...",
    "sha256": "...",
    "label": "A"
  },
  "option_b": {
    "artifact_ref": "...",
    "sha256": "...",
    "label": "B"
  },
  "choice": "A|B|tie|neither",
  "reason_tags": ["identity", "accuracy"],
  "note": "optional bounded explanation"
}
```

Prefer references/hashes over duplicating large response/image payloads.

## Relationship to existing paired evaluation

Human preference and numeric scoring answer different questions.

For a candidate capability:

- deterministic scorer -> objective/machine acceptance signal;
- human comparison -> subjective/product-preference signal;
- workflow signal -> recurrence/governance signal.

They may be synthesized, but one must not silently impersonate the other.

A human preference can become one scored datum in a deliberately defined benchmark, but the conversion rule must be explicit and fixed before looking at results.

## Promotion boundary

One preference receipt is evidence, not a permanent personal rule.

Durable promotion should use current learning semantics:

- repeated evidence where appropriate;
- direct promotion only for an explicitly requested stable preference or another already-authorized exception;
- existing ownership/roadmap checks before changing product behavior.

No receipt automatically changes:

- model routing;
- system prompts;
- Image Lab defaults;
- Builder policy;
- memory authority.

## Privacy/minimization

Store only what the comparison requires.

For images:

- use artifact/reference identifiers and hashes;
- avoid copying private source images into evaluation records.

For conversations:

- use bounded excerpts only when needed;
- otherwise bind the response artifact/hash.

A preference evidence record should remain useful even if the underlying private asset is intentionally removed.

## Suggested first application

The strongest first use is **Image Lab paired evaluation**, because subjective identity fidelity and appearance preferences often need direct human comparison while InsightFace supplies a separate machine score.

A single evaluation can therefore preserve:

- exact reference lock hash;
- candidate A/B hashes;
- engine/model/settings;
- InsightFace scores;
- explicit human A/B/tie/neither choice;
- bounded reason tags.

That creates analyzable evidence without teaching a hidden optimizer to mutate Image Lab automatically.

## Acceptance for a future implementation

1. both options are exact-identity/hash bound;
2. ordering can be randomized when bias matters;
3. tie/neither are first-class choices;
4. missing underlying artifacts do not become fabricated content;
5. storage is bounded and private-data-minimized;
6. preference evidence never changes production behavior by itself;
7. any promotion uses the existing learning/ownership boundary.
