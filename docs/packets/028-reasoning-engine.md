# 028 — Reasoning Engine

**Status:** 📋 spec authored 2026-07-14, not built
**Activation:** `active_packet` — but life-first work (ADR 0016) and the
Builder reliability chain (026/027) outrank it for build time
**Best executor:** Claude Code / Codex; Part C slices are bounded enough for
a free OpenCode worker once #176 lands
**Intent:** when Kitty's model brain thinks, Jacob can see the thinking; Kitty
gets an execution mode she can set per situation; and an optimization layer
makes every answer cheaper and sharper — right context in, right model for
the job, honest confidence out.

## What this is (Jacob's words, decoded)

Three things, one engine:

1. **Show the reasoning.** Reasoning models (Claude extended thinking,
   DeepSeek R1, OpenAI o-series) produce a thinking trace today and Kitty
   throws it away — Jacob literally cannot see why the model said what it
   said. Kitty shows it, collapsed, above the answer.
2. **Control the reasoning.** An execution mode — **Auto / Fast / Balanced
   / Deep** — that maps to each model's native knob. Jacob can set it;
   Auto (the default) lets Kitty's classifier pick, falling back to
   Balanced when classification is uncertain.
3. **Optimize around the model.** The engine enhances the other models'
   answers and cuts wasted tokens: classify the question's complexity before
   dispatch, spend memory-context budget to match, route to the cheapest
   model that can do the job, and flag low-confidence answers on the way
   out. It works **with** the model — less garbage in, honest signal out.

## Where this came from (and what got corrected)

This is **Wave 4 of the "chat cutting edge" plan** plus that plan's items 2a
and 3e, originally sketched as `docs/packets/026-chat-cutting-edge.md` on
branch `claude/kittybuilder-dogfood-preflight-bif2qb` (PR #164, closed
unmerged 2026-07-13 during repo stabilization; branch preserved as prior
art). Renumbered to 028 because main's registry had already assigned 026 to
Builder reliability — the third numbering collision, see L-CAND-13.

The full archaeology of PR #164 — what it built, what survives on main,
what gets recovered where — is in `docs/plans/pr164-archaeology.md`. The
built-but-lost Wave 1–3 features (thread goals, memory visibility, signal
cards, model override) are tracked there as the `chat-recovery-v1` plan,
**not** in this packet.

Premises corrected against main, 2026-07-14:

1. ~~Waves 1–3 of the cutting-edge plan are on main~~ — **none of it is.**
   PR #164 died whole: migrations stop at `019_idea_mine.sql`, no reasoning
   passthrough anywhere. The reasoning-display and mode-control work is
   therefore **in scope here**, rebuilt from a clean branch, not assumed.
2. ~~The gateway filters reasoning blocks out; "just stop filtering"~~ —
   **wrong layer.** `iter_chat_completions_stream()`
   (`gateway/llm_client.py:809`) already passes SSE chunks through
   verbatim. The drop happens in the frontend:
   `gateway/kitty-chat/src/lib/chat-client.ts:63` reads only
   `delta.content`. And nothing ever *requests* thinking — no
   `thinking`/`reasoning_effort` params are sent, so most models never emit
   a trace to begin with.
3. ~~Post-flight self-review goes in `self_review.py`~~ — **wrong module.**
   That file is voice-drift/reaction logging feeding `SOUL_SCRATCHPAD.md`.
   Answer-quality review lives in the new `gateway/reasoning.py`.
4. ~~Context sharpening "saves 30-60% of memory tokens on average"~~ —
   **invented number.** Restated below as a measurement this packet must
   produce, not a premise it assumes.

## Intake classification

- **Class:** `active_packet`
- **Why this is not just an idea:** every seam already exists and was
  verified this session — the SSE passthrough, `route_model()`
  (`gateway/llm_client.py:716`, a keyword list), `assemble_context()`
  (`gateway/context_assembler.py:224`) spending a flat
  `CONTEXT_TOKEN_CAP = 1200` (`gateway/memory_graph.py:42`) on every
  message, `Item.score` computed by stores and ignored at assembly.
- **Why now / why later:** move-in day is reached; this is depth-track work.
  It serves NORTH_STAR §3 directly — Kitty runs on free/cheap routes, and
  this engine is the mechanism that keeps expensive calls rare, deliberate,
  and visible. It still queues behind life-first initiative work and
  Builder 026/027: it makes Kitty better at answering, it doesn't move
  Jacob's life forward by itself.
- **Activation trigger:** already active; build order per the registry's
  depth track.

## Demo contract

- [ ] **See it think:** Jacob asks a real question in `Deep` mode, and a
      collapsed "thinking" block renders above Kitty's answer in chat —
      expand it, read the model's actual trace. Lowercase, collapsible,
      mono — per design canon.
- [ ] **Turn the knob:** flip the mode Fast / Balanced / Deep on the same
      question and watch the answer (and the thinking block) change; leave
      it on Auto and see the classifier's pick in the receipt. On a model
      with no reasoning support the control visibly does nothing — never
      faked.
- [ ] **Watch it save:** `jq 'select(.metadata.tier != null)'
      data/kitty_token_log.jsonl | tail` shows per-tier prompt-token
      counts — "thanks kitty" measurably stops paying for 1200 tokens of
      memory context.
- [ ] **Catch a weak answer:** a deep question that gets a two-line evasive
      answer produces a `low_confidence` row in
      `data/kitty/reasoning_log.jsonl` with the reason named.

## Why this exists

- **The thinking is invisible.** Jacob's paying (in tokens or trust) for
  models that reason, and the reasoning never reaches him. When Kitty says
  something surprising, there's no way to check *why*.
- **Routing is a keyword list.** `route_model()` sends anything matching
  `_REASONING_KEYWORDS` ("why", "explain"…) to Sonnet and everything else
  to DeepSeek flash. "Why not!" pays for Sonnet; a ten-paragraph decision
  question without the magic words gets the cheap model.
- **Context is flat-rate.** Every message formats up to 1200 tokens of
  memory into the prompt, filtered only by `memory_policy.should_surface()`
  — a privacy/staleness gate, not a relevance ranker.
- **Nothing looks at the answer.** A deep question answered with one
  evasive line, a response born from two provider fallbacks, a prompt
  assembled while memory stores errored — all exit looking identical to a
  good answer.

## Product principle

> Kitty shows her work and spends like it's her own money. The engine works
> **with** the model — sharper context in, the cheapest model that can do
> the job, the thinking visible, honest confidence out. Every decision it
> makes is logged with its trigger; a low-confidence flag is a flag, never a
> silent retry.

## Relationship to existing machinery (read before building)

- **`iter_chat_completions_stream()`** — already verbatim passthrough; Part
  A's backend work is parameter injection, not stream surgery.
- **`route_model()`** — Part C extends it; do not build a rival router. Its
  keyword sets become one signal among several in the classifier.
- **`gateway/council.py`** — the multi-task supervisor (ANALYZE → ROUTE →
  VERIFY → SYNTHESIZE). The original sketch's "pre-flight decomposition"
  item is the Council's job and is **dropped from this packet**. The
  reasoning engine is strictly per-message.
- **`domain_router.classify_domain()`** — already computed per request; the
  classifier may use domain as a signal but must not re-classify it.
- **`gateway/token_usage_log.log_llm_usage()`** — already appends to
  `data/kitty_token_log.jsonl` and takes a `metadata` dict; telemetry rides
  it, no new token log.
- **`/perf/stats`** (`gateway/routes/perf.py`) — the existing surface for
  aggregates; per-tier stats extend it.
- **Privacy boundary** — `enforce_privacy_boundary()` in `llm_client.py` is
  untouched. Level and tier only pick among already-permitted models.
- **Design canon** (`design-system/v2-reference/KITTY.md` + behavioral laws
  in `design-system/PHILOSOPHY.md`): thinking block is lowercase,
  collapsible, mono on `--surface-2`, collapsed by default, no exclamation
  marks. Don't redraw the cat.

## The slices (execution order; each is one bounded PR)

### Part A — show the reasoning

**A1 — request + parse the trace.** Backend: when the effective mode wants
thinking (Balanced/Deep) and the resolved model supports it, inject the
model-native param into the
LiteLLM payload (`thinking: {type: "enabled", budget_tokens: N}` for
Claude-family, `reasoning_effort` for OpenAI o-series — LiteLLM translates;
DeepSeek R1 emits `reasoning_content` unprompted). Support map lives in one
dict in `gateway/reasoning.py`, keyed by LiteLLM alias, env-overridable.
Frontend: `chat-client.ts` additionally yields
`delta.reasoning_content ?? delta.thinking ?? ''` as a separate `thinking`
field; `types.ts` message type grows `thinking?: string`.

**A2 — render it.** `ChatMessage.tsx`: collapsed "thinking" section above
the answer body when `thinking` is non-empty — hairline border, lowercase
label with duration if known, mono text, collapsed by default, state
persists per message while the session lives. Vitest per component;
verified live in the browser (screenshots) — UI is not done from code
inspection.

### Part B — control the reasoning

**B1 — the mode.** `auto | fast | balanced | deep`, three places it can
come from, in precedence order: per-message override (UI) → per-thread
setting → **Auto**, the default (decided by Jacob 2026-07-14). Auto means
the Part C1 classifier picks; when classification is uncertain, Auto
behaves as Balanced. Until C1 lands, Auto = Balanced flat. Backend accepts
`reasoning_mode` on the completions payload, validates it, maps it through
the A1 support table (fast → no thinking params; balanced → model default
budget; deep → high budget/effort — #164's concrete numbers were 4096 /
16000 `budget_tokens` for Claude and medium/high `reasoning_effort` for
o-series; keep them as starting values). UI: a quiet control in
`InputBar.tsx` or `TopBar.tsx` (executor picks the less cluttered spot,
canon: lowercase, no new chrome); disabled state — not hidden, visibly
inert — when the active model has no reasoning support.

**B2 — the budget guard (Jacob, 2026-07-14).** Deep is hard-capped per
turn at roughly 2–3× Balanced's token budget, enforced where the payload
is built. Automatic escalation (classifier or fallback deciding to go
higher than the user asked) moves **at most one step** and never
automatically enters paid-deep beyond that. Cap hits and escalations are
logged in the receipt (C5) — never silent, never faked down.

### Part C — the optimization engine

**C1 — complexity classifier + adaptive routing.** New
`gateway/reasoning.py`: `classify_complexity(message, domain) ->
Classification` with `tier: trivial | standard | deep` and `trigger: str`
(which signal decided — always set, always logged). Pure heuristic, no
model call, <1ms: length, question structure, imperative-vs-smalltalk,
absorbed `_REASONING_KEYWORDS`/`_BEST_TRIGGERS`, domain nudge
(benefits/health lean deep). `route_model()` delegates:
trivial/standard → `kitty-default`, deep → `kitty-sonnet`
(`KITTY_REASONING_MODEL` overrides the deep alias). Under Auto, the
classifier also sets the mode (trivial→Fast, standard→Balanced,
deep→Deep, uncertain→Balanced), which an explicit Part B choice
overrides. Honest note: v1 is three tiers, two model
outcomes — trivial's payoff is C2's smaller context spend.

**C2 — tier-aware context budget.** `assemble_context()` grows an optional
`tier` param (default `standard` preserves current behavior byte-for-byte —
test asserts it). Memory cap per tier: trivial 300 / standard 1200
(unchanged) / deep 2400, flowing into `_format_memory_block()`.
Optional enrichments (weather, calendar…) are **skipped by default on
the trivial tier** and included only when directly relevant to the message
(decided by Jacob 2026-07-14); standard/deep keep today's enrichment
behavior.

**C3 — memory relevance re-rank.** Before formatting, rank policy-filtered
items: `Item.score` where the store provided one, keyword overlap with the
message, recency from `Item.ts`; drop below a floor before they eat the
cap. Deterministic pure Python — embedding re-rank via Chroma is a named
follow-on, not smuggled in. `memory_policy.should_surface()` untouched;
this ranks what policy already allowed.

**C4 — post-flight confidence flag.** `review_response(message, response,
tier, warnings) -> ReviewFlag | None` in `gateway/reasoning.py`. Heuristics
only: deep tier + very short answer, provider fallback occurred,
`memory_graph:` warnings during assembly, answer parrots the question.
Flags append to `data/kitty/reasoning_log.jsonl` — tier, trigger, token
counts, correlation id, **no raw message or response bodies**. Flag also
rides the existing `log_chat_trace()` line and surfaces **inline** in the
chat UI as a quiet marker on the flagged message. **No push notifications
in v1** (Jacob, 2026-07-14: pushes would be noisy and misleading). No
auto-retry, ever.

**C5 — execution receipts + telemetry.** Every turn produces one receipt:
mode, tier, trigger, resolved model, token counts, cap-hit/escalation
flags, confidence flag, correlation id — as `metadata` on the existing
`log_llm_usage()` call sites plus the `log_chat_trace()` line, not a new
subsystem. Per-tier aggregates (count, prompt/completion tokens) in
`/perf/stats`. This produces the real answer to "how much does the engine
save" — the number the original sketch made up. Classifier thresholds are
tuned against a frozen labeled message set (reuse `gateway/eval_runner.py`
seams), so C5's numbers are measured against fixed ground truth.

## Scope budget

- **Expected diff size:** medium, spread over ~7 small PRs; no single slice
  over ~400 changed lines including tests
- **Expected files touched:** ~12 — `gateway/reasoning.py` (new),
  `llm_client.py`, `context_assembler.py`, `memory_graph.py`,
  `routes/completions.py`, `routes/ask.py`, `routes/perf.py`; UI:
  `chat-client.ts`, `types.ts`, `ChatMessage.tsx`, `InputBar.tsx` or
  `TopBar.tsx`; matching tests
- **Stop and split if:** the classifier wants a model call; a slice needs to
  change `memory_policy` semantics; re-ranking wants embeddings; the mode
  control wants per-model UI beyond enabled/disabled; any slice crosses the
  diff budget
- **Do not expand into:** Council decomposition, memory-visibility overlay
  ("kitty remembered…" — separate cutting-edge item), thread goals, SSE
  signal cards, embedding re-rank, new LiteLLM providers, prompt rewriting,
  automatic retry-on-low-confidence

## Privacy / sensitivity

- **Touches sensitive content?** yes — reads message text to classify;
  renders model thinking traces which may restate personal context
- **Content classes:** `chat`, `memory`
- **Cloud allowed?** no change — classification is local heuristic; mode
  and tier only select among models the existing privacy boundary permits
- **Forbidden:** raw message/response/thinking text in
  `reasoning_log.jsonl` or token-log metadata (render thinking, don't log
  it anywhere new); routing must never select a model the privacy tier
  forbids; no silent re-ask on low confidence

## Files likely touched

- `gateway/reasoning.py` (new) + `tests/test_reasoning.py` (new)
- `gateway/llm_client.py`, `tests/test_llm_routing.py`
- `gateway/context_assembler.py`, `tests/test_context_assembler.py`
- `gateway/memory_graph.py` (cap parameterization only)
- `gateway/routes/completions.py`, `gateway/routes/ask.py`, `gateway/routes/perf.py`
- `gateway/kitty-chat/src/lib/chat-client.ts`, `src/lib/types.ts`
- `gateway/kitty-chat/src/components/ChatMessage.tsx` + test
- `gateway/kitty-chat/src/components/InputBar.tsx` or `TopBar.tsx` + test

## Files not to touch

- `gateway/memory_policy.py` — privacy gate, not a relevance knob
- `gateway/council.py` — decomposition stays there
- `gateway/litellm_config.yaml` — no new aliases in v1; deep-tier override
  is env-only
- `gateway/self_review.py` — voice drift is a different organ
- `.env`, `config/action_tiers.json`, anything auth
- `kid-cat.svg` — obviously

## Acceptance criteria

1. With a reasoning-capable model in `Deep` mode, the thinking trace
   renders in chat, collapsed by default; in `Fast` mode, no reasoning
   params are sent and no block renders. Verified live in the browser with
   screenshots, not from code inspection.
2. The mode control is visibly disabled (not hidden, not faked) on models
   without reasoning support, per the A1 support table; Deep respects the
   per-turn budget cap and the one-step escalation limit, with a test on
   the payload builder.
3. `classify_complexity()` covered by table-driven tests including
   adversarial cases: short message with a reasoning keyword, long message
   with none, smalltalk containing "why".
4. With no tier passed, `assemble_context()` output is byte-identical to
   pre-packet behavior (test asserts it).
5. Receipt rows carry mode/tier metadata; `/perf/stats` returns per-tier
   aggregates; the close-out note states the *measured* trivial-vs-standard
   prompt-token delta.
6. `reasoning_log.jsonl` rows contain no message/response/thinking bodies
   (test inspects a written row).
7. Suites green: `python3.12 -m pytest tests/ -q --tb=short`, `make ui-test`,
   `make ui-build` (never `npm run` — exit-194 trap), ruff on touched files.

## Verification commands

```bash
python3.12 -m pytest tests/test_reasoning.py tests/test_llm_routing.py tests/test_context_assembler.py -q
python3.12 -m pytest tests/ -q --tb=short
make ui-test && make ui-build
jq 'select(.metadata.tier != null)' data/kitty_token_log.jsonl | tail -5
./kitty doctor --json
```

## Review artifacts

- Screenshots: thinking block expanded + collapsed, day and night themes;
  mode control in its enabled and disabled states
- Terminal: the two-message demo (trivial vs deep) with gateway log lines
  showing tier, model, and context size
- The measured per-tier token numbers, from real log rows

## Decisions (Jacob, 2026-07-14 — these gated the build and are now set)

1. **Deep-tier spend:** hard per-turn cap at roughly 2–3× Balanced, no
   automatic paid escalation beyond one step (→ B2).
2. **Default mode:** Auto — classifier picks, Balanced when uncertain
   (→ B1/C1).
3. **Trivial-tier enrichments:** skip optional enrichments by default;
   include weather/calendar/etc. only when directly relevant (→ C2).
4. **Confidence flags:** inline + operational log only; no push in v1 —
   pushes would be noisy and misleading (→ C4).

## One-line build instruction

Build the reasoning engine — visible thinking traces (A), Auto/Fast/
Balanced/Deep execution modes honestly mapped to model-native knobs with a
budget guard (B), and the per-message optimization layer with execution
receipts in `gateway/reasoning.py` (C) — one slice per PR in the order
above, without touching memory policy, the Council, or anything in the
do-not-expand list, and close out with measured per-tier token numbers
instead of the invented ones.
