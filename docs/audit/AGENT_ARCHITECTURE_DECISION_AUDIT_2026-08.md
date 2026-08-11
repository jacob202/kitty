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
float; results below `TRIAGE_CONFIDENCE_FLOOR` are meant to reroute to
`needs_jacob` instead of being trusted (module docstring: "There is no
rule-based fallback... fail loud, never guess").

**Correction (caught in PR review, not compliant as originally written):**
`_parse()` (`triage.py:165`) does `confidence = float(data["confidence"])`
with no range or finiteness check, and `_classify()` (`triage.py:129`) only
tests `confidence < TRIAGE_CONFIDENCE_FLOOR`. Two malformed-model-output
cases both slip past the floor instead of triggering it:

- an out-of-range value like `70` (model ignored the requested `0.0-1.0`
  scale) is not `< 0.6`, so it's treated as high-confidence;
- `NaN` (or any value `float()` accepts but a comparison can't order) is
  never `< 0.6` either — Python's `NaN < x` is always `False` — so a
  garbled model response is silently trusted rather than caught.

This is exactly the class of thing AAA-1 is supposed to surface: the design
intent ("fail loud, never guess") is right, but the implementation doesn't
enforce it against malformed input. **Not proposing the fix here** (that's
implementation, out of scope for this audit pass per #390's own
instruction not to perform a broad refactor) — flagging it as a named,
concrete follow-up: validate `0.0 <= confidence <= 1.0` and finite in
`_parse()`, raising the same fail-loud error the module already uses for
other malformed output.

### 4. `gateway/memory_weave.py` — `confidence` field

Used for provenance/decay and conflict resolution between stored facts —
composition is deterministic (`CORRECTION_BOOST` and decay are fixed
constants), not a live per-call LLM ranking decision. **Compliant.**

### 5. `gateway/query_builder.py` — unrelated

Grep hit was `f"column {column!r} has non-alphanumeric...` — false positive
from the word "score" not appearing; excluded after read. No decision logic
here at all (it's a SQL where-clause builder).

### 6. `gateway/magic_kitty.py` — prompt-requested `confidence`

**Missed by the original grep** (pattern list didn't catch this phrasing;
caught in PR review). The prompt at `magic_kitty.py:76` asks the model for a
`"confidence": 0.0 to 1.0` field per cross-project connection found. No code
in the module reads `data["confidence"]` back out to gate, rank, or filter
anything — it appears to be a display/provenance field only. Listed
explicitly now rather than silently absent from this audit; not excluded by
verified behavior, excluded because no consuming code was found.

### 7. `gateway/librarian.py` — `authority_score`

**Also missed by the original grep.** The model returns `authority_score`
(`0.0-1.0`), which the module normalizes if it's on a 1-5 scale instead
(`librarian.py:142-152`) but otherwise doesn't visibly route, rank, or gate
behavior with — same caveat as `magic_kitty.py`: no confirmed consumer found
in this module, not proven inert everywhere the value flows to. Listed
explicitly; a full trace of where `authority_score` is read downstream (UI
sort order? filtering threshold?) is unverified and out of scope here.

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
decision from categorical inputs. Three more surfaces carry a bare
LLM-emitted number (`triage.py`, `magic_kitty.py`, `librarian.py`) — this
audit's grep pattern list missed the latter two on the first pass, which is
itself evidence this kind of search needs more than one keyword set to
trust as complete. Of the three, only `triage.py`'s confidence is confirmed
to gate a real decision (routing to `needs_jacob`), and that gate has a
concrete validation gap (see above). `magic_kitty.py` and `librarian.py`'s
numbers have no confirmed downstream consumer in the modules that produce
them, but "no consumer found in this file" is not the same claim as "proven
inert" — a full call-site trace wasn't done.

## Net finding

Kitty has at least one surface (`triage.py`) using a bare LLM-emitted number
to gate a real decision, and the intended fail-closed design has a concrete
hole: malformed model output (out-of-range or NaN confidence) slips past
the floor instead of triggering it. Two more numeric fields exist
(`magic_kitty.py`, `librarian.py`) without a confirmed behavioral effect.
AAA-1's "start with one high-value surface" now has a real, named candidate:
fix `triage._parse()`'s confidence validation. No refactor is applied by
this pass, consistent with #390's instruction not to perform a broad
refactor here — but unlike the original version of this document, the
starting point is a genuine gap, not a clean bill of health.
