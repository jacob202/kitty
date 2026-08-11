# Decision-surface audit — AAA-1 (#390)

Continues `docs/audit/AGENT_ARCHITECTURE_INVENTORY_2026-08.md` (AAA-0). Scope
per #390: "find every LLM-generated score/confidence/risk/ranking that
directly determines behavior. Replace unsafe direct numeric decisions with
categorical schemas + deterministic composition where it materially improves
correctness. Start with one high-value surface... Do not perform a broad
refactor." This pass is the search — no refactor is proposed here.

## Method

Grepped `gateway/*.py` and `gateway/routes/*.py` for `score`, `confidence`,
`risk_score`, `priority_score`, and numeric-scale patterns (`1-10`, `/10`,
"out of 10"), then read every hit that wasn't a test file.

## Surfaces found

### 1. `gateway/action_queue.py` — `risk_tier` (T0/T1/T2)

Categorical, closed set, loaded read-only from `config/action_tiers.json`
(signed off by Jacob per the file's own docstring), enforced in the executor
registry. Not model-assigned per call. **Compliant — no change.**

### 2. `gateway/compute_governor.py` — `risk_class`

Categorical, validated against `RISK_CLASSES` (`compute_governor.py:235`), a
`blocker` class requires named evidence, not a number
(`compute_governor.py:252`). **Compliant — no change.**

### 3. `gateway/triage.py` — bucket + confidence float

`run_pass()` asks an LLM for a bucket (categorical) **and** a confidence
float; results below `TRIAGE_CONFIDENCE_FLOOR` reroute to `needs_jacob`
instead of being trusted (module docstring: "There is no rule-based
fallback... fail loud, never guess").

This is the one surface in the codebase where a bare LLM-emitted float
participates in a decision. It's a narrower case than what #390 warns
against, though: the float doesn't rank or select an action, it only gates
whether the model's own categorical answer is trusted enough to act on, and
the fallback on low confidence is "ask Jacob," not "guess anyway." Still
worth naming explicitly since it's the one place a raw model number touches
the decision path.

**Disposition for AAA-1's own criteria: acceptable as-is.** Not proposing a
change — swapping the float for a categorical confidence tier (e.g.
`high|medium|low`) would remove the last bare number from the codebase, but
`TRIAGE_CONFIDENCE_FLOOR` already fails to `needs_jacob` rather than acting
on a bad guess, so the risk the rule exists to prevent isn't present here.
Flagging it is the deliverable; changing it would be scope creep past what
this pass was asked to do.

### 4. `gateway/memory_weave.py` — `confidence` field

Used for provenance/decay and conflict resolution between stored facts —
composition is deterministic (`CORRECTION_BOOST` and decay are fixed
constants), not a live per-call LLM ranking decision. **Compliant.**

### 5. `gateway/query_builder.py` — unrelated

Grep hit was `f"column {column!r} has non-alphanumeric...` — false positive
from the word "score" not appearing; excluded after read. No decision logic
here at all (it's a SQL where-clause builder).

## Surfaces checked and confirmed absent

- `gateway/image_plan.py`, `gateway/image_guidance.py` — no confidence/score
  field; #390 named "image-plan readiness" as a candidate surface, but
  nothing there currently emits a model-driven readiness number to check.
- `gateway/routes/*.py` — no route assigns a `risk_tier`/`risk_class` value
  itself; both origins are `gateway/builder_loop.py:625` (a hardcoded
  literal `"routine"`, not model output) and `compute_governor.py:674`
  (read from the caller's typed payload, validated on the way in).

## Answer to AAA-0's open question

AAA-0 asked whether `action_queue.py` and `compute_governor.py` are the only
two decision surfaces in scope. They're the only two that **compose** a
decision from categorical inputs. `triage.py` is a third surface worth
tracking because it's the only place a bare model confidence number exists
at all — but per the finding above, it's already fail-closed and doesn't
need the same fix. Nothing else in the codebase does model-driven
routing/approval/escalation on a raw number.

## Net finding

Kitty has one (not zero) surface using a bare LLM-emitted number, and it's
already the safe pattern (float gates a fallback to human, never authorizes
an action on its own). AAA-1's "start with one high-value surface" doesn't
have an unsafe candidate to start with — the audit itself is the finding.
No refactor is proposed by this pass, consistent with #390's instruction not
to perform a broad refactor here.
