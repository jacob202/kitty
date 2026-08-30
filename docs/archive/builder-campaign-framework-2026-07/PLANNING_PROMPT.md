# Prompt for Opus 4.8 / Fable 5 — KittyBuilder daily-driver roadmap + design + audit

You are acting as Jacob's systems-design thinking partner for Kitty, his local-first
single-user AI companion app (`~/Projects/kitty`: FastAPI gateway, Next.js UI, LiteLLM
model routing). This is a planning session, not an execution session — you are not
expected to write code. Produce a written plan that Jacob will hand to Claude Code
(running Sonnet 5) to execute afterward, so the output needs to be concrete enough to
turn directly into Builder packets/tasks, not just prose.

Challenge assumptions where warranted — don't just agree with the framing below if a
better approach exists. Jacob's own house style for this project (from Kitty's
CLAUDE.md) is: fail loud, verify before claiming done, keep diffs small, no silent
scope creep, no unrequested abstractions. Apply the same discipline to this plan itself
— don't propose a bigger system than the problem needs.

## Ground truth: where KittyBuilder actually is today

KittyBuilder is Kitty's autonomous coding/implementation subsystem — the thing that
takes a described feature/fix and builds it. This is grounded in a code+docs audit
performed 2026-07-21, not assumption:

**Shipped and working (phases KB-S1A through KB-S4):**
- A durable SQLite-backed task queue (`gateway/builder_queue.py`,
  `builder_queue_db.py`) with a strict state machine (queued → claimed → running →
  pr_opened → awaiting_review → done, plus blocked/failed/cancelled), lease-fenced
  mutations, and append-only events.
- An initiative/packet system (`gateway/builder_initiative.py`): versioned JSON
  manifests of ordered work packets with objectives, acceptance criteria, allowed-path
  scopes, dependencies, and retry policy (`max_attempts`). Applying a manifest
  atomically materializes one queue task per packet; dependency graph is
  topologically validated with blocked-forever detection.
- A bounded execution loop (`gateway/builder_loop.py`, `builder_runner.py`): per
  packet — isolated git worktree, worker subprocess, optional reviewer subprocess,
  deterministic validation against declared test commands, bounded repair loop.
  **Runs in shadow mode throughout — no auto-push, no auto-merge, every run ends in
  an operator decision.**
- Identity/scope enforcement (`gateway/builder_identity.py`, `builder_scope.py`):
  fail-closed — a worker that touches paths outside its allowed scope gets stopped
  and returns structured evidence, not a silent widening of scope.
- CLI: `./kitty builder queue ...` (25 subcommands) and
  `./kitty builder initiative ...` (16 subcommands) — this is genuinely usable
  today for manual dogfooding (add a task, claim it, run it, publish a PR for human
  merge).
- 201 files / 47k LOC in `gateway/`, 191 test files / 37.7k LOC, 2,681 tests passing
  as of the last full run.

**Explicitly NOT done yet (cited from `docs/PROJECT_STATUS.md`,
`docs/ARCHITECTURE.md`, `docs/KITTYBUILDER_QUICKSTART.md`,
`docs/KITTYBUILDER_SELF_BUILDING_MVP.md`):**
1. **No autonomous Mission ingress.** Kitty's own agent loop
   (`gateway/agent_runner.py`) cannot hand a mission to Builder automatically — ADR
   0017 defines the contract, nothing implements the ingress side. Jacob manually
   runs `queue add` / `initiative apply` today.
2. **No planning/clarification phase.** Builder only executes pre-authored packets.
   It cannot take "I want to build X feature," ask clarifying questions, decompose
   it into packets, or negotiate scope with Jacob before starting. A human (or a
   separate paid-model session) has to author the packet manifest by hand first.
3. **No prototype-first step.** Each packet goes straight from
   implement → validate → review → repair. There's no "show a rough draft, confirm
   direction, then build for real" phase before committing to a full implementation.
   (Note, verified 2026-07-21: the *gating mechanism* for this already exists —
   `builder_initiative.eligible_packets` only satisfies a dependency when the
   upstream task reaches `done`, and `done` requires human merge. A prototype
   packet that everything else `depends_on` is therefore a hard human gate with
   zero schema change. What's missing is the convention, authoring support, and
   prototype-grade acceptance criteria — not runtime machinery.)
4. **KB-S5 (continuation loop, budgets, pause/resume) is closer to done than the
   docs imply.** Verified 2026-07-21 against code: `builder_run.run_initiative`
   already enforces per-initiative attempt and runtime budgets (pausing with a
   stated reason), per-packet attempt budgets come from `policy.max_attempts`
   (`builder_initiative._attempts_exhausted`), pause/resume ship as CLI commands
   (`initiative pause` / `initiative resume`), and restart reconciliation runs at
   loop start (`recover_expired_leases` + `recover_interrupted_runs`). What KB-S5
   still lacks is the *judgment layer* the abandoned campaign framework designed:
   the kill-switch asymmetry (real ambiguity halts; routine failures don't), the
   escalate-vs-retry thresholds, and health metrics. Also lacking: a verified
   dogfood pass marking KB-S5 ✅ in `docs/KITTYBUILDER_SELF_BUILDING_MVP.md`.
   Treat the framework as raw material for that judgment layer, not as a parallel
   system to bolt on.
5. **No merge automation** (by design so far, but worth re-litigating) —
   `queue publish` opens/updates a PR; a human merges.
6. **Read-only investigation UI only** — all mutations are fenced CLI operations,
   there's no UI for triggering/monitoring a run.
7. **No artifact/log delivery design** — safe, bounded delivery of logs/transcripts/
   diffs back to Jacob or to Kitty's own context is explicitly listed as unavailable
   by design, not yet solved.

A prior independent estimate (from the code-audit pass, treat as a rough anchor not
gospel) put items 1, 5, and 7 at roughly 4-6 weeks combined for one capable agent
working in packets. It did not estimate items 2, 3, and 4 (the planning/prototype/
campaign-lifecycle work) — that's a big part of what this session needs to size.

## Raw material: the abandoned campaign governance framework

A previous attempt (branch `codex/campaign-p1-05`, forked 2026-07-14, stalled
2026-07-15 after completing 3 of a planned 31 packets, never resumed) built an
orchestration-layer design for running Builder as a multi-agent "campaign" with
minimal supervision. Its runtime code was superseded by what's live in `gateway/`
today, but its **process design was never reproduced anywhere else** and is
genuinely relevant to gaps #2, #3, and #4 above. It's archived verbatim (not yet
integrated into anything) at:

```
docs/archive/builder-campaign-framework-2026-07/
  README.md                          — context and status
  GOVERNANCE.md                      — doc ownership/review/deprecation process
  BUILDER_CAMPAIGN_CONTROLLER.md     — state machine, kill switch, retry policy,
                                        escalation thresholds, merge evidence gate,
                                        phased rollout, retrospective template
  BUILDER_CAMPAIGN_ORCHESTRATOR.md   — the orchestrator's own operating prompt
  BUILDER_IMPLEMENTATION_CAMPAIGN.md — a 31-packet work graph example
  campaign_state.json                — actual run state at the point it stalled
```

Read these in full before designing anything. Key mechanisms worth stealing (adapt,
do not copy verbatim — file paths and script names inside these docs reference a
doc structure kitty no longer has):
- The kill switch: hard-stop conditions (two workers colliding on the same file, a
  packet needing architectural judgment beyond its scope, a reviewer rejecting the
  same packet twice on architectural grounds, systemic validation regression) vs.
  the explicit "these do NOT trigger a stop" list (test failures, merge conflicts,
  worker stalls — just retry/reassign). The asymmetry is the valuable part: it
  stops the orchestrator from crying wolf on routine failures while still halting
  hard on real ambiguity.
- Escalate-vs-don't-escalate thresholds (3 workers failing the same packet the same
  way = ambiguous requirement, escalate; 1-2 failures = just retry).
- Phased rollout discipline: run one phase, write a retrospective, check health
  metrics (merge success rate, first-pass review rate, kill-switch count) before
  authorizing the next phase — never launch all work at once.
- It literally stopped itself correctly once (blocked on P1-03, an unresolved
  architecture question, rather than guessing) — that's evidence the design works,
  not just theory.

## What Jacob actually wants built (the target behavior)

A "campaign" = one feature/fix request, from "I want to build X" to shipped. Jacob
wants:

1. **A clarification round.** Given a feature request, Builder should spend one
   round figuring out what's actually being asked for — including asking Jacob
   clarifying questions when the request is ambiguous — before any implementation
   work starts. This is currently 100% missing (gap #2 above).
2. **A prototype gate for anything big enough to warrant it.** If the feature is
   substantial, produce a working prototype first specifically so design flaws and
   misunderstandings become visible before the full build, not after. Small
   packets can skip straight to full implementation. Define "big enough" concretely
   — don't leave it as a vibe.
3. **Two invocation shapes he wants to be able to test: short vs. long, and free vs.
   paid.** "Short" and "long" likely map to campaign scope (one packet vs. a
   multi-phase build); "free" maps to the existing zero-cost OpenCode worker path
   (`docs/FREE_WORKERS.md`) vs. paid-model workers. Confirm this mapping makes sense
   given what's actually in the codebase, or propose a better one.
4. **This should be testable/runnable in a way Jacob can actually exercise it** —
   he explicitly wants to be able to run a normal/long/free/short campaign and
   inspect the output, not just read a spec. The plan should include how he tests
   this end to end, not just what gets built.
5. **The underlying campaign/continuation runtime should also work standalone**,
   outside a full "ask KittyBuilder to build a feature" flow — e.g. so Jacob can
   invoke just the bounded-execution-with-retry-and-kill-switch machinery directly
   to fix something narrow, without going through a clarification/prototype gate
   that doesn't apply. Don't force every use case through the heaviest path.

## Deliverables

Produce a single written plan with these sections:

1. **Campaign lifecycle design.** Concrete state machine for
   clarify → (prototype if warranted) → implement → validate → review → repair →
   publish, showing exactly where it attaches to the *existing* queue/initiative
   state machine in `builder_queue.py`/`builder_initiative.py` rather than replacing
   it. Specify the "big enough for a prototype" threshold concretely (e.g. packet
   count, LOC estimate, number of files touched, presence of new UI surface —
   whatever's actually decidable from a manifest before work starts). Show where
   the archived kill-switch/escalation/retry design plugs into finishing KB-S5,
   with specific file/function-level touch points where you can infer them from the
   module descriptions above.
2. **Roadmap to daily use, as packets.** Break the remaining work (mission ingress,
   clarification phase, prototype gate, KB-S5 completion, artifact delivery, and
   anything else you think is load-bearing) into an ordered set of packets sized
   the way Builder's own manifest format expects (objective, acceptance criteria,
   rough scope). Give a realistic time/effort estimate per packet and in total —
   Jacob wants "how much work is actually left," not optimism.
3. **Test plan for the four campaign shapes** (short/long × free/paid, or your
   corrected mapping) — what Jacob actually runs and looks at to confirm each shape
   works, once built.
4. **Light audit / challenge.** You have enough context here to poke at the current
   design. Specifically consider: Is shadow-mode-everywhere (no auto-merge, ever)
   still the right default once a clarification+prototype gate exists upstream of
   it, or does added upstream confidence justify loosening it for small packets?
   Is running planning/clarification as a Builder-internal phase the right call, or
   should that live in Kitty's main agent loop with Builder staying purely an
   execution engine? Is the packet/manifest format expressive enough to encode
   "this needs a prototype gate" and acceptance-criteria-for-a-prototype, or does it
   need extending? Where does this design risk recreating the abandoned campaign's
   own failure mode (stalling on an unresolved architecture question with no path
   to resolve it other than "ask Jacob")? Flag anything where the honest answer is
   "this adds process weight without proven payoff yet" — Jacob does not want a
   speculative framework, he wants something he actually uses daily.

## Constraints

- Ground every claim in the actual files listed above — cite paths. If you're
  inferring rather than certain, say so explicitly.
- Don't just re-propose the archived framework wholesale. It was designed for a
  31-packet from-scratch campaign; adapt the parts that solve gap #2/#3/#4, drop or
  flag the parts that don't fit KittyBuilder's actual current shape (e.g. its docs-
  governance section assumes a doc structure that doesn't exist anymore).
- Optimize for something Jacob will actually run this week, not a five-phase
  meta-project. If the honest scope is smaller than what's described above, say so
  and cut it down — do not pad the plan to look more substantial.
