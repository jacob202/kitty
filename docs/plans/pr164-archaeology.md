# PR #164 Archaeology — what died, what survived, what to recover

**Date:** 2026-07-14 · **Method:** every claim below verified against
`origin/main` @ `9d9a1ad` and branch
`claude/kittybuilder-dogfood-preflight-bif2qb` @ `0cbe40a` (PR #164's head,
preserved). Merge-base `771dbd4`. Diff: 47 files, +2,386/−246, 18 commits.
PR #164 is treated as historical evidence, not a merge candidate.

A load-bearing correction first: **PR #164's description undersold its own
branch.** The body says "Wave 1+2", but the commits go through Wave 3 —
goal sidebar, reasoning level config, memory correction, per-message model
override, and SSE signal cards were all implemented (`0cbe40a`, `9e48a3f`,
`ec95fb4`). And **Wave 4 (the reasoning engine) was never code** — it exists
only as a spec section inside the branch's packet file. So the branch is the
opposite of what memory suggests: waves 1–3 are *built and lost*, wave 4 was
*never built at all*.

---

## 1. Executive summary

**What survived on main:** every backend seam #164's UI leaned on already
exists — `DELETE /memories/{id}`, `/signals/unprocessed` +
`/signals/{id}/dismiss`, the `/stream` SSE endpoint with
`signal_store.emit()` broadcasting `state_updated`, and the
`useActiveProject`/`useProjectNext`/`useDeadlines` query hooks. The route
modules its 90 contract tests target (artifacts, experts, integrations,
memories, runtime) are all live. Nothing from #164 itself merged.

**What was lost:** all of it. Reasoning display, reasoning level knob,
thread-scoped goals (migration + CRUD + PATCH + UI), memory visibility
trailer + block, inline memory correction, goal sidebar, signal cards +
SSE hook, per-message model override, model-aware context budget, the
fail-loud sweep across 11 modules (zero of its log lines are on main —
verified line-by-line; main's TL-05 sweep covered *different* modules:
memories/monitors), the coverage ratchet, and ~974 lines of route contract
tests covering five route modules that today have **no tests at all**.

**What should be recovered:** the fail-loud sweep (trivially, first), the
route contract tests (re-validated against today's routes, then the CI
ratchet as a follow-up), thread goals, signal cards, memory visibility +
correction, and per-message model override — as small separate PRs under a
new chat-recovery initiative, not one big resurrection.

**What should never be recovered:** `context_cap_for_model()` as designed
(it *inflates* token spend — see §5), the coverage number `65` as a
cherry-pick, the brittle substring-based reasoning support map
(`"o1" in model.lower()`), the branch's STATE/HANDOFF/PROJECT_STATUS
rewrites, and its packet file (superseded by packet 028 for Wave 4; its
Wave 1–3 content is superseded by this report's recovery plan).

**On Wave 4:** #177 recovers the *plan* correctly and improves it (four
false premises struck, council overlap resolved, invented numbers replaced
with measurement obligations). What #177 deliberately does **not** cover —
and what this archaeology exists to keep from vanishing — is the built
Wave 1–3 feature set. That becomes its own recovery track (§6).

---

## 2. Feature inventory

| Feature | Purpose | Files touched (#164) | Status on main | Recommendation |
|---|---|---|---|---|
| Reasoning display (frontend parse + ThinkingBlock) | Show model thinking traces collapsed above the answer | `chat-client.ts`, `types.ts`, `ChatMessage.tsx`, `page.tsx` | **Missing** — `chat-client.ts:63` still drops everything but `delta.content` | Recover via packet 028 Part A; #164's ThinkingBlock (~80 lines) is sound reference material |
| Reasoning level knob (`_reasoning_params()` + TopBar `ReasoningSelector`) | off/normal/deep → `thinking.budget_tokens` / `reasoning_effort` | `routes/completions.py`, `types.ts`, `TopBar.tsx` | **Missing** | Rewrite via 028 Part B — the mapping logic is right, the support detection is unsafe (see §3) |
| Thread-scoped goals | `objective` column + CRUD + PATCH + prompt injection | `migrations/026_chat_objective.sql`, `chat_lifecycle.py`, `routes/chats.py`, `context_assembler.py`, `page.tsx`, `TopBar.tsx`, `gateway.ts` | **Missing** — main's migrations stop at `019`, no `objective` anywhere | Recover, mostly as-is; renumber migration from main (020 is next free — the branch's "026" is its own numbering drift) |
| Memory visibility (trailer + MemoryBlock) | "kitty remembered…" — which memory items informed the answer | `routes/completions.py`, `chat-client.ts`, `ChatMessage.tsx`, `types.ts` | **Missing** | Recover redesigned — trailer protocol is fine; the implementation double-filters (see §3) |
| Inline memory correction | Delete a wrong memory from the chat surface | `ChatMessage.tsx` (MemoryBlock delete), `gateway.ts` | **Missing** (frontend); `DELETE /memories/{id}` **already on main** | Recover with UX care — #164 deleted with no confirm/undo; destructive one-tap on phone is a footgun |
| Goal sidebar (`GoalSidebar.tsx`) | Project/deadline/objective panel per thread | `GoalSidebar.tsx` (new, 144 lines), `page.tsx` | **Missing**; all three data hooks exist on main | Park — needs Jacob's UX call; overlaps HomeState, and phone-first (D12) has no sidebar room |
| Proactive signal cards + SSE hook | Expert signals render as cards in chat, pushed live | `lib/sse.ts` (new), `SignalCard.tsx` (new, 146 lines), `page.tsx` | **Missing** (frontend); backend fully live (`signal_store.py:83` broadcasts, routes in `routes/experts.py:15,58`) | Recover — highest-leverage lost feature; backend is waiting for it |
| Per-message model override | "this message: <model>" chip in InputBar | `InputBar.tsx`, `page.tsx` | **Missing** | Recover small, bundled with reasoning-knob UI work |
| Model-aware context budget (`context_cap_for_model()`) | Scale memory cap to 4% of model context window (800–16K) | `memory_graph.py`, `context_assembler.py` | **Missing** | **Do not recover** — superseded by 028's tier-aware budget; see §5 |
| Fail-loud sweep (11 modules) | Log 11 silent `except` blocks | `cron`, `librarian`, `pdf_pipeline`, `clerk`, `eval_runner`, `expert_state`, `expert_proactive`, `brief`, `nudge`, `honcho`, `app` | **Missing** — 0 of its log lines present on main; TL-05 (#167) covered `memories`/`monitors`, different modules | Recover first — pure additive logging, zero behavior change |
| CI: coverage 10%→65%, drop `--ignore` flags | Make the pytest gate honest | `.github/workflows/tests.yml` | **Missing** — main still at `--cov-fail-under=10` with both ignores | Recover the *intent*: land tests first, measure, ratchet to the measured number; verify the ignored council tests pass before un-ignoring |
| Route contract tests (~90 tests, 974 lines) | HTTP-layer coverage for artifacts/experts/integrations/memories/runtime routes | 5 new test files + `test_chat_completions.py` additions | **Missing** — those five route modules have no tests on main today | Recover — re-run against today's routes before trusting; routes evolved during stabilization |
| tsconfig: exclude `playwright.config.ts` | Unblock typecheck | `tsconfig.json` | **Missing**, but typecheck is green on main today | Fold into the next UI PR touching tsconfig; not worth its own change |
| Continuity check → `.claude/HANDOFF.md`; README handoff refs | Point tooling at the real handoff file | `scripts/check_continuity_state.py`, `README.md`, `START_HERE.md` | **Missing** — script still reads `docs/AGENT_HANDOFF.md` | Needs a one-time canon decision (two handoff files exist); then trivial |
| Doc reconciliation (registry dedupe, statuses) | Fix the drifted packet registry | `docs/packets/README.md`, `docs/PROJECT_STATUS.md` | **Superseded** by #177 (registry merged, 026/027/028 rows added) | Done; nothing to recover |
| Packet 026-chat-cutting-edge spec | The plan document itself | `docs/packets/026-chat-cutting-edge.md` | **Superseded** — Wave 4 by packet 028; Waves 1–3 by §6 of this report | Do not restore the file; its number was never main's to begin with (L-CAND-13) |
| STATE/HANDOFF/PROJECT_STATUS rewrites | Session bookkeeping of a dead session | `.claude/*`, `docs/PROJECT_STATUS.md` | Historical | Never recover |
| `.gitignore` `.claude/worktrees/` | Ignore agent worktrees | `.gitignore` | **Missing** (main ignores `.worktrees/`, a different path) | Trivial; fold into any chore PR |

---

## 3. Code recovery analysis (Missing items only)

**Reasoning display.** Effort: small (frontend parse is ~10 lines;
ThinkingBlock ~80). Risk: low — additive rendering. Dependencies: none on
main (gateway already passes SSE verbatim); pairing with the level knob is
what makes traces actually appear, since most models emit nothing unless
asked. Cherry-pick: **no** — `page.tsx` diverged (the branch is 15+ merges
behind and its page.tsx hunk is 206 lines of a 1,100-line monolith).
Rewrite against 028 Part A, with the branch open in a second pane.

**Reasoning level knob.** Effort: small. Risk: **medium** as written —
`modelSupportsReasoning()` does substring sniffing (`"o1" in lower`
matches any model id containing "o1"), and `_reasoning_params()` duplicates
the same sniffing server-side; the two can disagree. Rewrite per 028 Part
B: one support table keyed by LiteLLM alias, exposed to the UI, both sides
reading the same truth.

**Thread goals.** Effort: small. Risk: low — additive column, guarded
CRUD, clean PATCH endpoint; the `assemble_context(objective=…)` injection
is 8 lines. Cherry-pick: **backend yes, with two fixes** — renumber the
migration from main's table (020, not 026), and re-run its lifecycle tests.
Frontend header UI: rewrite (page.tsx drift).

**Memory visibility.** Effort: small-medium. Risk: medium — #164's stream
wrapper buffers `[DONE]`, emits the trailer, then releases it; that
reordering touches the hot path of every chat. Its trailer also re-filters
`bundle.memory_items` through `should_surface()` — but the assembler
*already* policy-filters; re-filtering the unfiltered `memory_items` list
was compensating for `ContextBundle` exposing pre-filter items. The clean
fix is exposing post-filter items on the bundle, not filtering twice.
Rewrite, keeping the trailer wire format (it's good: after content, before
`[DONE]`, `{"memory_items": [...]}` with 200-char truncation).

**Inline memory correction.** Effort: tiny (backend exists). Risk: medium
UX — irreversible delete, one tap, phone-first. Add a confirm step or a
grace-period undo before shipping. Rewrite (it's ~30 lines).

**Signal cards + SSE hook.** Effort: small-medium. Risk: low-medium — the
`useSSE` hook is clean (52 lines, reconnect logic); risk concentrates in
page.tsx wiring. Dependencies: none — backend routes and broadcast are
live on main *today*. Cherry-pick: `sse.ts` and `SignalCard.tsx` yes
(self-contained new files); page wiring rewrite.

**Per-message model override.** Effort: small. Risk: low. Must respect the
privacy boundary (override only among models the tier permits — reuse the
existing `enforce_privacy_boundary` path, which #164 did implicitly by
passing through `route_model`'s output; make it explicit). Rewrite.

**Fail-loud sweep.** Effort: trivial. Risk: none worth naming — additive
`logger.warning/error` lines in existing `except` blocks. Cherry-pick:
feasible file-by-file, but the hunks are so small that re-applying by hand
against today's files is faster than resolving 15 merges of drift.

**Route contract tests.** Effort: small (files are additive). Risk:
medium — they encode the routes' *July-12* behavior; stabilization landed
#165–#175 since. Cherry-pick the five files, run them, and treat every
failure as a question ("did the route change intentionally?") rather than
editing tests to green. Budget a half-session for that reconciliation.

**CI ratchet.** Effort: trivial mechanically, risky blindly. The 65%
number was measured *with* the branch's ~1,000 added test lines; applying
it to today's main without them will likely fail the gate. Sequence:
tests land → measure → set the ratchet at measured-minus-margin → separately
verify `test_council_graph.py` / `test_mcp_council_server.py` pass before
removing their ignores (they were excluded for a reason nobody wrote down).

---

## 4. Wave 4 comparison (#177 vs #164)

#164 contains **zero Wave 4 code** — no `gateway/reasoning.py`, no
classifier, no tier routing. Its Wave 4 is 40 lines of spec inside the
packet file. So the comparison is plan-vs-plan:

**Identical:** the core thesis (classify before dispatch, sharpen context,
route by complexity, review after, measure tokens) and the design
principle ("works with the model, not against it") — #177 keeps both.

**Improved in #177:** four false premises corrected against code
(`self_review.py` misfit; wrong-layer "gateway filters reasoning"; waves
1–3 assumed present; invented 30-60% savings figure now a measurement
obligation); decomposition ceded to `council.py` instead of duplicated;
privacy constraints made explicit (no bodies in new logs); do-not-touch
list; slice-per-PR structure with diff budgets; the level knob and
reasoning display pulled *into* the packet (they were separate waves in
#164, which is how they got lost).

**Missing from #177 (by design, now needing a home):** everything in §2
marked "recover" that isn't reasoning display/knob — thread goals, memory
visibility, memory correction, signal cards, model override, fail-loud,
tests/CI. #177's do-not-expand list correctly keeps them out of packet
028; without this report they'd be orphaned. §6 gives them one.

**Regressed:** nothing identified. One nuance: #164's `_reasoning_params()`
already handled the o-series `reasoning_effort` mapping concretely; 028
should keep that concrete mapping (budget numbers included: 4096 normal /
16000 deep were #164's picks) rather than re-deriving it.

**Beyond either PR** (now decided by Jacob, 2026-07-14):

- **Execution modes** replace the raw level knob: **Fast / Balanced /
  Deep / Auto**, default **Auto** — classifier picks; uncertain
  classification falls back to Balanced behavior.
- **Budget management:** hard per-turn spend cap for Deep ≈ 2–3× Balanced;
  automatic escalation limited to **one step**, never automatically into
  paid-deep beyond that.
- **Trivial-tier enrichments:** skip optional enrichments (weather,
  calendar…) by default; include only when directly relevant.
- **Confidence reporting:** inline + operational log only. **No push
  notifications in v1** — pushes would be noisy and misleading.

These are folded into packet 028 alongside this report.

---

## 5. Architecture review

**Builder / initiative system.** Recovered features fit the current
delivery machinery well: each is packet-shaped (bounded paths, testable,
one PR). Recommendation: register the recovery as an initiative manifest
(`docs/initiatives/chat-recovery-v1.json`) mirroring `trust-lane-v1`, so
free workers can execute slices under the existing queue/review gates.
Nothing recovered may touch Builder internals.

**Council.** No conflicts — none of the recovered features decompose
tasks. Packet 028 already cedes decomposition to `council.py`.

**Current routing (`route_model`).** The per-message model override must
be layered *above* `route_model` (explicit human choice beats heuristic)
but *below* the privacy boundary (no override into a forbidden model). #164
got the ordering right in practice; make it a stated invariant.

**Memory graph / context assembler.** Thread-goal injection and the
post-filter `memory_items` fix are compatible and small. The one
architectural rejection: **`context_cap_for_model()` should not return.**
Scaling the memory budget to 4% of the context window means a 1M-window
Gemini gets a 16,000-token memory block *on every message* — 13× today's
spend, driven by model capacity rather than message need. That is the
exact inversion of NORTH_STAR §3 economics. 028's complexity-tier budget
(spend follows the *question*) supersedes it. Salvage at most the
model-window table as a *ceiling clamp* (never exceed 4% of window), which
only matters for tiny-window models.

**Model routing config.** The reasoning support map must be keyed by
LiteLLM alias (one table, server-owned, UI reads it), not substring
matching duplicated in two languages.

**Receipts.** There is no receipts system in the gateway (verified —
"receipt" appears nowhere); the Builder's run manifests are the closest
analog. Chat should get a lightweight per-turn **execution receipt** —
mode, tier+trigger, model, token counts, cap-hit flag, confidence flag,
correlation id — as an extension of the existing `log_chat_trace()` +
`token_usage_log` rows, not a new subsystem. This is 028's C4/C5 slightly
widened, and it gives the recovered UI features something honest to
display later.

**Redesign-instead-of-restore verdicts:** reasoning support detection
(alias table), memory trailer (post-filter bundle field), memory
correction (confirm/undo), context budget (tier-based, window as ceiling
only). Restore-approximately-as-was: thread goals backend, fail-loud
lines, contract tests, `useSSE`/`SignalCard` components.

---

## 6. Recommended recovery plan

Small PRs, in this order. "Packet" numbers to be taken from the registry
at authoring time per the intake gate — the numbers below are placeholders.

| # | Item | Priority | Size | Depends on | Risk | Initiative | PR scope |
|---|---|---|---|---|---|---|---|
| R1 | Fail-loud sweep, 11 modules | P1 | XS (~25 lines) | — | none | standalone chore | one PR, logging lines + one regression test per converted path (TL-05 pattern) |
| R2 | Route contract tests, 5 files | P1 | S (additive) | — | med (route drift) | standalone chore | one PR; reconcile failures as route questions, not test edits |
| R3 | CI ratchet: measured coverage + un-ignore council tests if green | P1 | XS | R2 | med | standalone chore | one PR, after measuring on post-R2 main |
| R4 | Thread goals (migration 020 + lifecycle + PATCH + header UI) | P2 | S | — | low | chat-recovery-v1 | backend PR, then UI PR |
| R5 | Signal cards + `useSSE` in chat | P2 | S-M | — | low-med | chat-recovery-v1 | one PR; cherry-pick the two new files, rewrite page wiring |
| R6 | Memory visibility (trailer + block, post-filter bundle fix) | P3 | M | 028 C-slices help but not required | med (hot stream path) | chat-recovery-v1 | backend trailer PR, then UI PR |
| R7 | Inline memory correction (+ confirm/undo) | P3 | XS | R6 | med UX | chat-recovery-v1 | one PR |
| R8 | Per-message model override | P3 | S | privacy-boundary invariant stated | low | chat-recovery-v1 | one PR, may bundle with 028 Part B UI |
| R9 | Goal sidebar | P4 / parked | S | R4 | UX unknown | parked | only on Jacob's explicit call (D12 phone-first makes sidebars suspect) |
| R10 | Hygiene: tsconfig exclude, `.claude/worktrees/` ignore, handoff-file canon | P4 | XS | canon decision on handoff file | none | fold into adjacent PRs | no standalone PR |

Packet 028 (reasoning engine) proceeds independently on its own track —
its Parts A/B overlap R-items only at the UI seams, and the slices are
ordered so they don't collide.

---

## 7. Wave 4 improvements (applied to packet 028)

Adopted from Jacob's decisions and this review — packet 028 is updated in
the same PR as this report:

1. **Execution modes** — user-facing control becomes **Auto / Fast /
   Balanced / Deep**, default Auto. Auto = classifier's pick; uncertain →
   Balanced. (Replaces off/normal/deep; "off" survives as Fast's thinking
   behavior — no reasoning params sent.)
2. **Budget guard** — Deep is capped per turn at ~2–3× Balanced's token
   budget; automatic escalation moves at most one step and never
   automatically enters the paid-deep tier beyond that. Cap hits are
   logged, never silent.
3. **Trivial/Fast enrichments** — optional enrichments skipped by default;
   included only when directly relevant to the message.
4. **Confidence reporting** — inline + log only; no push in v1.
5. **Execution receipts** — C4/C5 widen into one per-turn receipt row
   (mode, tier, trigger, model, tokens, cap-hit, confidence) so the
   optimizer's behavior is auditable from day one.
6. **Evaluation** — the classifier gets a frozen labeled message set
   (reuse `gateway/eval_runner.py` seams) so threshold tuning in C5 is
   measured against fixed ground truth, not vibes.
7. **Provider/tool routing** — explicitly out of scope for v1; the engine
   selects among existing LiteLLM aliases only. Tool routing stays with
   the Council/agent layer.

Challenged assumption worth recording: the original KRE sketch treated
"more context = better answers" and "bigger window = spend more" as
axioms. The measured-receipts design exists to test the opposite: most of
Jacob's messages should get *less* context and a *cheaper* model with no
quality loss. If receipts show otherwise, the thresholds move — that's the
point of making them measurable.

---

## 8. Final recommendation

**Directly recover (cherry-pick with re-validation):** the five route
contract test files (R2); `lib/sse.ts` and `SignalCard.tsx` (R5); the
thread-goals backend with migration renumbered (R4). These are additive,
self-contained, and their targets on main are verified live.

**Rewrite (keep the design, redo the code):** reasoning display + level
knob (via packet 028 Parts A/B, alias-keyed support table); memory
visibility trailer (post-filter bundle fix); memory correction
(confirm/undo); per-message model override (privacy invariant explicit);
fail-loud lines (faster to retype than rebase); CI ratchet (re-measured).

**Abandon:** `context_cap_for_model()` as designed (economics inversion);
the coverage number as a constant; substring model sniffing; the branch's
session-state files; the `026-chat-cutting-edge.md` packet file itself.

**Separate initiatives:** `chat-recovery-v1` (R4–R8, manifest-registered
so free workers can run it) and the three standalone chores (R1–R3),
which need no initiative ceremony.

**Wave 4 stays packet 028** — the reasoning engine (visible thinking,
Auto/Fast/Balanced/Deep modes, budget-guarded optimizer, receipts),
updated with the seven improvements above. It is a *successor* to #164's
sketch, not a recovery of it: the only thing Wave 4 ever had was a plan,
and the plan is now better.

Nothing in #164 needs to merge for any of this. The branch stays preserved
as reference; this report is its tombstone and its will.
