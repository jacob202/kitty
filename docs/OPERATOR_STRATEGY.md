# Kitty — Recovered Thesis and Execution Strategy

**Date:** 2026-07-01
**Status:** Product archaeology + operating model + 30-day execution path.
**Relationship to other docs:** This does not replace `docs/DECISIONS.md` or
`docs/ARCHITECTURE.md`. It recovers the product thesis those docs serve and
proposes the next spine of work. Decisions extracted from this document must
land in `docs/DECISIONS.md` before any packet ships.

---

## 1. Executive verdict

The repo is a better foundation than its docs admit, and a smaller product
than its own soul requires.

The last quarter built the floor: one SQLite story (`data/kitty/kitty.db` with
migrations), one read path (`memory_graph`), a thin write seam
(`storage_router`, D7), blocking CI (ruff + mypy + pytest, 671+ tests), a
launcher and doctor, a real design system. That work was correct and is done.

What was never built is the thing Kitty is supposed to be. Today Kitty is a
chatbot with good memory, a morning brief, and a persona. It cannot answer
"what is the current state of things," cannot say "here is what changed since
yesterday," cannot triage what comes in, cannot prepare an action for
approval, and cannot see the two highest-signal feeds in Jacob's life (email,
GitHub). The initiative engine (`nudge.py`), the background hands (`cron.py`,
`researcher.py`, `web_monitor.py`), the user model (`config/USER/` TELOS), and
the delegation seed (`domain_router.py`, `llm_client.py`) all exist as organs
with no nervous system connecting them. Meanwhile two UI panels — loops and
insights — serve **hardcoded fake data** (`gateway/routes/loops.py:12`,
`gateway/routes/insights.py:12`), which violates the repo's own first
non-negotiable and is the clearest symptom of the gap: the interface performs
an operating layer that the backend does not have.

Verdict: stop consolidating, stop polishing, and build the state + action
spine. Every piece needed for it already has a seed in the repo. The next 30
days decide whether Kitty becomes an operating layer or stays a well-built
chat app with a nice cat.

---

## 2. Recovered product thesis

**One sentence:** Kitty is the single trusted front door that maintains the
live state of Jacob's life and projects, tells him what changed and what
matters, and converts that into prepared, approvable actions — with all state,
memory, and preferences kept local.

**The deeper category:** not "AI assistant," not "AI companion." Kitty is a
**personal operating layer** — a control plane for one person's life. Its
parts are a state store, a continuity engine, a capture-and-triage loop, an
action queue with approval tiers, and a delegation router that hands work to
the right model or tool. The companion persona (SOUL.md) is the interface
contract — the voice and taste through which the operating layer speaks — not
the product itself.

**What already points at this thesis in the repo:**

- `gateway/brief.py` — the one existing "state synthesis" surface (calendar,
  weather, journal themes, news, memory snippet).
- `data/inbox.jsonl` + `desktop_store.py` + D4 — capture as an append-only
  front door that must survive everything else breaking.
- `gateway/nudge.py` — an initiative engine (repeated research, dropped
  threads, milestones) already written, barely surfaced.
- `gateway/cron.py`, `researcher.py`, `web_monitor.py` — background hands with
  scheduling and change detection.
- `config/USER/` (TELOS: mission, goals, problems, projects) — a user model
  injected into context; the reference frame triage needs.
- `gateway/domain_router.py` + `llm_client.py` — model routing with fallback;
  the seed of the delegation model.
- `gateway/autonomy_state.py` — persistent state for long multi-turn work.
- `docs/FUTURE_VISION_AND_ROADMAP.md` Pillar 3 ("It acts... judgment about
  act-vs-ask") — names the action layer explicitly; nothing implements it.
- The agent-ops discipline itself (AGENT_HANDOFF, LEARNINGS, packet-shaped
  phases B/C) — Kitty's own development process is a working prototype of the
  continuity + delegation loops the product needs.

---

## 3. What Kitty is / is not

**Kitty is:**
- The one front door: everything enters through capture, everything surfaces
  through state.
- State-first: context before chat; the home screen answers "what's going on"
  before any message is typed.
- Continuous: resumes, never restarts — for Jacob's projects, not just chats.
- An actor with boundaries: prepares actions, executes only inside approved
  tiers, records everything.
- Local-first: state, memory, preferences, and the control layer live on the
  Mac; cloud models are rented reasoning, never the system of record.
- Honest, with taste: SOUL.md's no-flattery, name-the-pattern spine is a
  product trait, not decoration.

**Kitty is not:**
- A therapy, coping, or recovery app. Attention to Jacob's patterns stays —
  as an operator's situational awareness, not as the product identity.
- A mascot toy. The cat is a state gauge (per `KITTY 2.md`: "a gauge with a
  face"); the state machine behind the face is the product.
- A generic chatbot with plugins, or an autonomous agent swarm.
- A dashboard for its own sake. Panels that display without enabling action
  (or that fake their data) are cut.
- A ten-year privacy startup. `FUTURE_VISION_AND_ROADMAP.md` explains *why*
  the near-term work matters; it is not a build target.

---

## 4. What is left on the table

1. **"What changed."** Kitty snapshots nothing, so it can diff nothing. The
   single most valuable sentence an operator says — "since you last looked:
   X" — is currently impossible.
2. **Triage.** Inbox entries carry `processed: false` and nothing consumes
   it. Capture works; nothing decides now / later / never / needs-Jacob.
3. **Prepared action.** No action queue, no approval tiers, no execution
   record. Everything Kitty "does" is chat output that evaporates.
4. **Email.** The highest-signal feed in daily life is unconnected. Calendar
   (AppleScript), weather, iMessage exist; mail does not.
5. **GitHub as data.** Jacob runs a multi-agent development operation on this
   very repo, and Kitty cannot see a PR, a failing check, or a review
   comment. The product is blind to its owner's most active workspace.
6. **Project state.** Resume-a-project is manual archaeology. (This document
   exists because of that gap.) Journal, chats, todos, and git each hold a
   shard; nothing composes them per project.
7. **Delegation artifacts.** Jacob hands packets to Codex/Claude Code daily
   by hand. Kitty — which routes models internally — cannot generate an
   executor-ready packet from its own action queue.
8. **Document ingestion.** `pdf_pipeline.py` exists; benefits/admin documents
   have no path into capture → knowledge → state.
9. **The nudge engine's output.** Nudges compute and mostly die unseen; they
   should be signals feeding the same queue as everything else.

---

## 5. Operating model

The conceptual system underneath everything else. Ten parts.

### 5.1 Current State model

At any moment Kitty maintains, queryable as one composed read (`/state/now`):

- **Commitments:** today's and upcoming calendar events, deadlines.
- **Open loops:** things started and not finished — untriaged inbox items,
  in-flight projects, awaiting-reply threads, actions awaiting approval.
- **Signals:** timestamped events from connectors (mail received, PR
  updated, monitor tripped, file dropped) — one append table, one shape.
- **Projects:** the registry of active projects with last-touched and status.
- **Identity/preferences:** TELOS + `config/PREFERENCES.md` (already wired).
- **Runtime health:** doctor status — the operator reports on itself.

State is *composed from* existing stores through `memory_graph` and the
dedicated store modules; it is not a new database. Only signals and snapshots
are new tables.

### 5.2 Continuity model

- Every session/day gets a cheap **state snapshot** (the composed
  `/state/now` JSON, persisted with a timestamp).
- "What changed" = structured diff of latest snapshot vs. previous, plus
  signals arrived in between. This powers the home screen's first strip and
  the morning brief's first paragraph.
- Open loops persist until explicitly closed — they are rows, not vibes.
- Session summaries (chats) and journal entries remain the narrative layer;
  snapshots are the mechanical layer. Continuity = mechanical diff + narrative
  thread, in that order.

### 5.3 Capture model

Unchanged in spirit (D4 stands), extended in reach:

- **One intake:** everything becomes an inbox entry — Raycast, Siri, Telegram,
  UI quick capture, forwarded email, screenshot, dropped file. Append-only
  JSONL survives everything else breaking.
- Files/screenshots/PDFs: the inbox entry stores a pointer + extracted text
  (via existing `pdf_pipeline.py` / `vision.py`), never a silent copy.
- Capture is dumb on purpose. No classification at write time. Enrichment is
  triage's job, seconds-to-minutes later.

### 5.4 Triage model

A scheduled + on-demand pass over untriaged inbox entries and unprocessed
signals. Output buckets:

- **now** — surfaces on home immediately; may spawn a proposed action.
- **scheduled** — becomes a todo/calendar hold with a date.
- **someday** — parked, resurfaced by the existing resurfacing loop.
- **reference** — filed to knowledge; findable, never nagging.
- **needs_jacob** — Kitty can't or shouldn't decide; lands in "Needs you."
- **drop** — noise; recorded as dropped, never deleted.

Triage decisions are rows keyed to the inbox entry id (JSONL itself stays
append-only). Each carries model, confidence, and rationale. Low confidence
⇒ `needs_jacob`, never a guess. If the classifying model is down, triage
fails loudly and entries stay untriaged — no rule-based fake fallback.

### 5.5 Action Queue model

An action is a first-class row, not a chat message:

`proposed → approved | rejected → executed | failed`, with
`source` (which signal/triage/nudge/chat spawned it), `kind` (typed:
`todo.create`, `calendar.event.create`, `email.draft`, `packet.delegate`,
…), `payload`, a human-readable `preview` (exactly what will happen),
`risk_tier`, and after execution a `result`. Every transition timestamped.
The queue is the audit log of everything Kitty ever did on Jacob's behalf.

### 5.6 Approval model

Four tiers, enforced in code at the executor, not by prompt discipline:

- **T0 — auto:** local, reversible, no external surface. Create/complete
  todos, file reference items, write local drafts and notes, update state.
  Executes immediately, still recorded in the queue.
- **T1 — draft:** produce the artifact, never transmit. Email replies, PR
  comments, messages, form fills. The draft is the deliverable.
- **T2 — approve-to-execute:** one explicit approval per action, then Kitty
  executes and records. Calendar event creation, sending a pre-approved
  draft, opening a GitHub issue.
- **T3 — never:** payments, deleting data, anything touching secrets/auth,
  bulk outbound of any kind, actions on accounts Kitty wasn't granted.
  Not "ask first" — structurally absent from the executor registry.

Tier assignments live in a reviewable config file Jacob signs off on, and a
kind's tier can only be lowered by editing that file — never at runtime.

### 5.7 Tool Connection model

Connectors are **read-first, poll-based adapters** that emit signals — they
never inject directly into chat or take actions:

- **Calendar** — exists (AppleScript). Reads feed state; `create` becomes a
  T2 action executor.
- **Mail** — new; read-only first (decision D-mail, §16). New/flagged
  messages become signals; replies exist only as T1 drafts until T2 is earned.
- **GitHub** — new; read-only API: PRs, checks, review comments on Jacob's
  repos become signals ("PR #57 has a failing check").
- **Files** — watched folders (e.g. an `~/Inbox` drop dir) → capture entries.
- **Notes/Reminders** — later, same pattern.
- **Web** — `web_monitor.py` already does change detection; its hits become
  signals instead of a dead-end table.

One pattern for all: cron-polled, emit signal rows with dedupe keys, fail
loud, no event bus until there are enough subscribers to earn one.

### 5.8 Project Resume model

A project is a registered entity: name, local path(s), status, last-touched,
rolling summary, open questions, next actions, delegable items, decision log
pointers. A **refresh** composes it from git log (for code projects), journal
mentions, chat sessions, todos, and signals. **Resume** returns the packet:
"status, what happened since you last touched it, open questions, next three
actions, what's delegable." The repo's own `docs/AGENT_HANDOFF.md` is the
hand-written prototype of this — the model is to mechanize exactly that
document per project.

### 5.9 Model Delegation model

Route by task class, not vibes — extending `domain_router`:

- **Local models (MLX):** persona chat, triage classification, summarization
  of private material that shouldn't leave the machine.
- **Sonnet-class cloud:** drafting (emails, briefs, summaries), routine
  enrichment where quality matters and content is approved to leave.
- **Opus/Fable-class:** planning, architecture, strategy, packet authoring,
  anything where being wrong is expensive.
- **Code executors (Codex, Claude Code):** never called "live" from chat —
  they receive **executor-ready packets** (title, scope, files, acceptance,
  verification) generated from the action queue, and their output comes back
  as PRs through normal CI + review.
- A privacy boundary rides the router: data classes (email bodies, journal,
  health/admin docs) are tagged local-only unless the specific task's
  approval says otherwise. This is decision D-privacy (§17).

### 5.10 Interface model

The home is the state system, not a chat window. Chat is one keystroke away
(the command palette already exists) but the front door answers before you
ask: what changed, what needs you, what's open, what's today. Every panel is
backed by a real endpoint over real rows — the fake loops/insights panels are
replaced or removed. The cat's four states map to the operating layer: idle
(nothing needs you), working (actions executing / triage running), done
(queue cleared), broke (a connector or executor failed — loudly).

---

## 6. North-star product shape

Morning: Jacob opens Kitty (or reads the Telegram brief). First strip: "since
last night — 2 emails need answers, PR #61 went green, the benefits form
deadline is in 3 days, nothing broke." Second strip: "needs you — 3 approvals:
a drafted reply to the landlord, a calendar hold for Thursday, a packet ready
to send to Claude Code for the journal migration." He approves two with two
clicks, edits the third. Capture bar is always there; during the day he throws
half-sentences, screenshots, and PDFs at it from Raycast, Siri, or his phone,
and never thinks about where they went. Opening the kitty project card tells
him where all four in-flight branches stand and which one is blocked on him.
At night, the wind-down brief closes the loops it can and names the one it
can't. Everything Kitty did on his behalf that day is a scrollable, auditable
queue. All of it lives on his Mac.

The loops, named:

- **Daily-use loop:** open → see state diff → approve/reject queued actions →
  capture throughout the day → wind-down closes loops → snapshot.
- **Project-resume loop:** open project → refreshed resume packet → pick next
  action → do it, or delegate it as a packet → resume record updates.
- **Action-on-behalf loop:** signal or capture arrives → triage → action
  proposed with preview + tier → auto (T0) / draft (T1) / approval (T2) →
  execute → record result → surface in "what changed."
- **Tool-routing loop:** task classified → local vs. cloud vs. executor
  decision (with the privacy boundary applied) → run → result and cost
  recorded (token accounting already exists in `token_usage_log.py`).

---

## 7. Smallest real version

The smallest Kitty that is *the real Kitty* and not a toy:

1. `/state/now` + snapshots + "what changed" diff (mechanical, no LLM).
2. Triage over the existing inbox, with the six buckets and `needs_jacob`.
3. The action queue with tiers enforced, and exactly three executors:
   `todo.create` (T0), `email.draft`/`message.draft` written locally (T1),
   `calendar.event.create` (T2).
4. Mail read-only + GitHub read-only connectors emitting signals.
5. A home surface showing: What changed / Needs you / Open loops / Today /
   Capture.
6. Project resume for three registered projects (kitty itself first).

That's it. No voice work, no new memory substrate, no autonomous anything.
It feels real because opening Kitty answers "what's going on," captured
things demonstrably come back, and actions get prepared and executed inside
visible boundaries. Every later ambition is this loop with more connectors
and more executor kinds.

---

## 8. Home base concept

Within the shipped v2 design system (manila/chalkboard, wobble, corner cat):

- **Top strip — What changed.** Diff since last open + significant signals.
  Each item links to its source. Empty state is honest: "quiet since 9pm."
- **Needs you.** The approval queue: each card = preview, tier badge, source,
  approve/reject/edit. This is the highest-value pixels in the product.
- **Open loops.** Real rows (untriaged count, in-flight projects,
  awaiting-reply, stale-but-alive), each with a next-step affordance.
  Replaces the fake loops panel.
- **Today.** Calendar + scheduled todos + brief link. Mostly read-only.
- **Projects.** Cards with last-touched + status; click → resume packet.
- **Capture.** The always-present input. Text now; file drop soon after.
- **Chat** is a drawer/palette summon, not the home. The conversation is one
  interface to the operating layer, and the layer shows its state either way.
- **The cat** reads queue + runtime state, per the four-state contract.

Panels that don't map to real rows don't ship. `PerfDashboard`, `DreamStatus`
and friends move behind a "system" view — they're operator tooling, not home.

---

## 9. Action queue and approval model

(Defined in §5.5–5.6; product commitments restated:)

- Every action Kitty takes — including T0 — is a recorded row with a preview
  of exactly what will happen and a result of exactly what did.
- Tiers are enforced at the executor registry in code. There is no code path
  from "model output" to "external effect" that bypasses the queue.
- T3 actions have no executor. A model asking for one gets a refusal from the
  system, not a judgment call from a prompt.
- Approvals are per-action. Standing rules ("always auto-file newsletters")
  are edits to the reviewable tier/rules config, made by Jacob, not learned
  silently.
- The queue is append-only history; rejected actions stay visible. That
  record is what makes trusting the next tier expansion rational instead of
  hopeful.

---

## 10. Project resume model

(Defined in §5.8; the concrete shape:)

- `projects` table: id, name, kind (code / admin / creative), paths, status,
  last_touched, summary, open_questions, next_actions, delegable, links.
- `refresh(project)` composes from: git (branch states, last commits, open
  PRs via the GitHub connector), journal + chats mentions (via
  `memory_graph`), todos tagged to the project, signals referencing it.
- `resume(project)` renders the packet: status line, what changed since last
  touch, decisions on record, open questions, next 3 actions, what's
  delegable right now.
- The kitty repo is project #1 — Kitty resumes its own development. This
  dogfoods the loop instantly (the data sources are all already local) and
  makes every future agent session start from Kitty instead of from
  `START_HERE.md` archaeology.
- Non-code projects (benefits/admin, job search) are the same table with
  document signals instead of git — that's the test that the model isn't
  secretly a dev tool.

---

## 11. Tool/model delegation model

(Defined in §5.9; the operating rules:)

- Routing is a table, not folklore: task class → allowed tiers of model →
  privacy class of data it may carry. Lives in config, versioned.
- Local-first is a default with teeth: triage, persona, and private-material
  summarization run local; if the local model is down, those tasks fail loud
  rather than silently escalating to cloud.
- Cloud reasoning (Sonnet/Opus/Fable-class) is for drafting, planning, and
  strategy — content either non-sensitive or explicitly approved to leave.
- Code executors receive packets, not conversations. A packet = title,
  purpose, exact scope, files, acceptance criteria, verification commands —
  the same discipline as §15, generated by Kitty from an approved action.
- Every delegation records cost and outcome. `token_usage_log.py` +
  `model_digest.py` already exist; wire them to the queue so "what did that
  cost" is answerable per action.

---

## 12. Repo reality check

**Supports the vision (keep, build on):**
- Gateway-is-the-product (D2) and thin clients — exactly right for one front
  door with many surfaces.
- `memory_graph` single read path (D3) — the state composer plugs into it.
- `kitty.db` + numbered migrations + per-store modules (D7 pattern) — the
  state/action/project tables follow this exactly.
- Capture (D4), brief, cron, nudge, web_monitor, TELOS, domain_router,
  doctor/launcher, blocking CI — all direct inputs to the spine.
- The agent-ops discipline (handoffs, learnings, small verified phases).

**Blocks or weakens it:**
- ~90 flat modules in `gateway/` with real overlap (`tasks.py`,
  `task_runner.py`, `task_boundary.py`; `agents.py`, `agent_runner.py`;
  `sync.py`, `honcho.py`) — navigation cost for every executor. Don't
  reorganize now; do stop adding to the pile (new spine = few, named modules).
- Fake-data routes (`loops.py`, `insights.py`) — actively corrosive: they
  train the UI (and Jacob) to distrust panels.
- AppleScript-only calendar — fine for now, but it sets a pattern; connectors
  need one shared shape (signals) before three more one-off integrations.
- Residual scatter: `web_monitors.db`, `autonomy_state.db`, JSONL logs — fine
  per D7, but signal-emitting things should converge on the signals table.
- `gateway/actions/` directory (three one-off scripts) squats on the name the
  action layer wants — rename or place the new module carefully
  (`action_queue.py`).

**Missing data model:** `signals`, `state_snapshots`, `actions`,
`inbox_triage`, `projects`. Five tables. That's the whole gap.

**Missing UI surface:** the state home (What changed / Needs you / Open
loops), approval cards, project resume view. `DashboardHome.tsx` is a
bootstrap-panels page, not a state console.

**Missing action/approval infrastructure:** all of it — queue, tiers,
executor registry, audit trail. Greenfield, by design (nothing to untangle).

**Stale or misleading docs:** `docs/PROJECT_STATUS.md` (dated 2026-06-20,
names branch `codex/phase-b-prep`; main has since merged #48–#56 including
the v2 design migration), root `TASKS.md` and `TODOS_NEXT.md` (reference
`ARCHITECTURE_COMPLETE.md`-era plans), `docs/KITTY_HUB.md` (a separate 5001
service that isn't the product), MemPalace docs (deferred path), desktop
phase-1 evidence docs (historical), root artifacts `KITTY 2.md`,
`tokens 2.css`, `Design system philosophy reimagine.zip`,
`kitty-studio-handoff.tar.gz` (loose exports at repo root).

**Test/CI gaps for remote-agent safety:** `mcp/` and `scripts/` outside
ruff/mypy globs (L-CAND-7 — one broken server already reached main);
no contract test pinning route registration + response shapes (a remote agent
can silently break `/state`'s contract for the UI); no migration-against-
seeded-db test (agents writing migration 006+ against an empty db can pass
tests and break Jacob's real `kitty.db`).

**What causes agent drift:** four planning surfaces telling different stories
(PROJECT_STATUS vs TASKS.md vs TODOS_NEXT.md vs handoff); three agent
rulebooks (AGENTS/CLAUDE/CODEX) duplicating rules that then diverge; stale
"next step is unclear" language in PROJECT_STATUS inviting each agent to
invent a direction; fake-data endpoints that make greps lie.

**Make canonical:** `START_HERE.md` → `docs/PROJECT_STATUS.md` (regenerated)
→ `docs/ARCHITECTURE.md` → `docs/DECISIONS.md` → this document → packet
registry (`docs/packets/`). One "current plan" pointer, everywhere else
tombstoned.

**Archive / demote (pending Jacob's confirmation for anything deleted):**
root `TASKS.md`, `TODOS_NEXT.md` → `docs/archive/`; `KITTY_HUB.md`,
MemPalace runbooks, desktop phase-1 docs → `docs/archive/`; root design
artifacts → `design-system/archive/` or out of the repo;
`FUTURE_VISION_AND_ROADMAP.md` stays, explicitly labeled "why, not what."

---

## 13. Multi-model execution strategy

- **Strongest reasoning model (Fable/Opus-class):** thesis and operating-model
  work (this document), schema design for the five tables, tier/rules config
  design, packet authoring, and review of any packet that touches approval
  boundaries or migrations.
- **Code-focused executors (Codex, Claude Code):** the packets in §15 —
  scoped, file-listed, acceptance-tested backend and UI work.
- **Sonnet-class:** doc cleanup and tombstoning, test backfill, small
  refactors, connector boilerplate once the first connector sets the pattern.
- **Reviewer model:** every PR gets CI (ruff, mypy, pytest, UI test+build —
  already blocking) plus a model review pass on the diff (the `/code-review`
  discipline; CodeRabbit already comments). Reviewer checks packet acceptance
  criteria specifically, not vibes.
- **Jacob approves:** anything changing approval tiers or the T3 list, any
  connector credential/scopes, the home-surface direction (once, at packet
  P4), any migration that alters existing tables, anything deleting files.
- **Never delegated blindly:** migrations against real data, auth/secrets
  handling, executor registry changes, tier config, force-pushes, doc
  archiving that deletes rather than moves.
- **Preventing conflicting plans:** one packet registry (`docs/packets/`),
  one packet = one branch = one PR; packets declare files-not-to-touch so
  parallel packets can't collide; PROJECT_STATUS regenerated at merge, not
  hand-drifted; L-CAND-1's concurrent-agent check stays in force.
- **Context between agents:** the packet file itself is the context — every
  packet carries purpose, scope, and verification inline so an executor needs
  zero archaeology. Project resume (P6) eventually mechanizes this.
- **Review chain before merge:** executor self-verifies (commands in packet)
  → CI green including check_runs, not combined status (L-CAND-6) → reviewer
  model on the diff → Jacob for the surfaces listed above → merge.

---

## 14. 30-day implementation path

**Week 1 — spine + honesty.**
- P1 (signals + snapshots + `/state/now`).
- Doc cleanup #1–2 (regenerate PROJECT_STATUS; tombstone stale planners).
- CI #1 (lint/type `mcp/` + `scripts/`).
- Remove or de-fake `loops.py` / `insights.py` fake data (fold into P1/P4).

**Week 2 — triage + queue.**
- P2 (inbox triage), P3 (action queue + 3 executors).
- CI #2–3 (contract test for `/state`; migration-on-seeded-db test).
- Jacob decisions D1–D3 (§16) locked into DECISIONS.md.

**Week 3 — the face + the feeds.**
- P4 (state home surface).
- P5 (mail read-only connector — decision-gated) and GitHub read-only signals
  (small; may ride P5's pattern or be P5b).

**Week 4 — continuity + delegation.**
- P6 (project resume, kitty repo as project #1).
- P7 (delegation packet generator).
- Brief rewired to open with the state diff (small follow-on to P1/P4).

Each week ends shippable; no packet depends on a later one.

---

## 15. First 7 executor-ready implementation packets

### P1 — State spine: signals, snapshots, `/state/now`

- **Best executor:** Claude Code or Codex (backend, test-heavy).
- **Purpose:** Give Kitty a queryable "now" and a mechanical "what changed."
- **Exact scope:** Migration `006_signals.sql`: `signals(id, ts, source,
  kind, payload_json, dedupe_key UNIQUE, processed_at)` and
  `state_snapshots(id, ts, snapshot_json)`. New `gateway/signal_store.py`
  (append, list-unprocessed, mark-processed, dedupe) and
  `gateway/state_composer.py` (compose now-state from: calendar today,
  untriaged inbox count + latest entries via existing stores, open todos,
  latest journal/chat timestamps via `memory_graph`, doctor summary; each
  source timeout-bounded like `brief.py`; snapshot + diff-vs-previous).
  New route `gateway/routes/state.py`: `GET /state/now`,
  `GET /state/changes`. Register in `routes/register.py`.
- **Files likely touched:** the above + `gateway/migrations/006_signals.sql`,
  `tests/test_signal_store.py`, `tests/test_state_composer.py`,
  `tests/test_state_route.py`.
- **Files not to touch:** `memory_graph.py` internals, `storage_router.py`,
  existing migrations, anything under `gateway/kitty-chat/`.
- **Steps:** migration → signal_store + tests → composer with bounded fan-out
  + tests → route + contract test → wire snapshot write into composer call.
- **Acceptance:** `GET /state/now` returns all sections with real data or an
  explicit per-section error (no fabricated values); `GET /state/changes`
  returns a structured diff after two calls; dedupe_key rejects duplicate
  signals; full suite green.
- **Verification:** `python3.12 -m pytest tests/ -q --tb=short`; `curl -s
  localhost:8000/state/now | jq .` locally.
- **Risks:** composer latency if a source hangs — bound every call; JSON
  payload column bloat — cap payload size, store pointers for big blobs.
- **Rollback:** migration adds tables only; revert the PR, tables are inert.
- **Unlocks:** P2, P3, P4, brief rewrite, all connectors.
- **Too broad if:** it grows an event bus, WebSocket push, or LLM summaries.
- **Jacob reviews:** the section list of `/state/now` — this defines "what
  Kitty knows."

### P2 — Inbox triage

- **Best executor:** Codex or Claude Code.
- **Purpose:** Make capture come back — decide now/later/never/needs-Jacob.
- **Exact scope:** Migration `007_inbox_triage.sql`:
  `inbox_triage(inbox_id UNIQUE, ts, bucket, confidence, rationale, model,
  status)`. New `gateway/triage.py`: load untriaged inbox entries, classify
  via `llm_client` (local-model route; TELOS + PREFERENCES in context),
  buckets `now|scheduled|someday|reference|needs_jacob|drop`; confidence
  below threshold ⇒ `needs_jacob`; LLM unavailable ⇒ raise, entries stay
  untriaged. Route additions: `POST /inbox/triage`, `GET /inbox/triaged?bucket=`.
  Cron entry (existing `cron.py` pattern) for a periodic pass.
- **Files likely touched:** above + `tests/test_triage.py` with fixture
  entries per bucket; `gateway/routes/desktop.py` or a new
  `routes/inbox.py`.
- **Files not to touch:** `data/inbox.jsonl` format, `desktop_store.py`
  write path (D4: capture stays dumb and append-only).
- **Steps:** migration → triage module with injected LLM callable → tests
  with a stub model → route → cron registration.
- **Acceptance:** fixture entries land in expected buckets with a stubbed
  model; real inbox entries never mutated; failure path verified (LLM down ⇒
  explicit error, zero rows written); suite green.
- **Verification:** `python3.12 -m pytest tests/test_triage.py tests/ -q`.
- **Risks:** over-eager `drop` — mitigate: `drop` is a bucket, never a
  deletion, and low confidence routes to `needs_jacob`.
- **Rollback:** revert PR; triage table inert; inbox untouched by design.
- **Unlocks:** action proposals from capture, honest "Open loops" counts.
- **Too broad if:** it starts proposing actions (that's P3's consumer) or
  adds new capture sources.
- **Jacob reviews:** bucket definitions + the confidence threshold.

### P3 — Action queue with enforced tiers

- **Best executor:** Claude Code (the tier enforcement deserves the
  strongest code executor); tier config reviewed by strongest model + Jacob.
- **Purpose:** The safe path from "Kitty thinks X should happen" to "X
  happened, recorded."
- **Exact scope:** Migration `008_actions.sql`: `actions(id, created_at,
  source_kind, source_id, kind, title, preview, payload_json, risk_tier,
  status, result_json, decided_at, executed_at)`. New
  `gateway/action_queue.py`: propose/approve/reject/execute lifecycle;
  executor registry mapping kind → (tier, callable); ships with exactly
  three kinds: `todo.create` (T0, via `todo_store` through
  `storage_router`), `note.draft` (T1, writes under `data/drafts/`),
  `calendar.event.create` (T2, via `calendar_integration.create`).
  Tier config `config/action_tiers.json` loaded read-only at startup;
  unknown kind or tier mismatch ⇒ hard error. New `gateway/routes/actions.py`:
  `GET /actions`, `POST /actions/propose`, `POST /actions/{id}/approve`,
  `/reject`, `/execute` (execute refuses non-approved T2, auto-runs T0).
- **Files likely touched:** above + `tests/test_action_queue.py`,
  `tests/test_actions_route.py`, `routes/register.py`.
- **Files not to touch:** `gateway/actions/` (legacy scripts — leave),
  `llm_client.py`, any external-sending code (none should exist).
- **Steps:** migration → queue module + registry → the three executors →
  routes → tests incl. tier-violation tests (a T2 execute without approval
  must 403; an unregistered kind must 400).
- **Acceptance:** lifecycle round-trips; tier enforcement proven by tests;
  every execution writes a result row; no executor exists for anything
  external beyond calendar-create.
- **Verification:** `python3.12 -m pytest tests/ -q --tb=short`; manual:
  propose → approve → execute a calendar event locally, see it in Calendar.
- **Risks:** scope creep into more executors — the registry makes additions
  one-line-visible in review; payload injection — validate payloads per kind
  with typed schemas.
- **Rollback:** revert PR; table inert; no external state beyond any
  calendar events Jacob approved (visible, manually deletable).
- **Unlocks:** P4's "Needs you," P5 drafts, P7 delegation, every future
  act-on-behalf feature.
- **Too broad if:** it adds email sending, GitHub writes, retries/scheduling
  of failed actions, or any "standing approval" logic.
- **Jacob reviews:** `config/action_tiers.json` line by line — this is the
  boundary document.

### P4 — State home surface

- **Best executor:** Claude Code (UI + design-system taste), after P1–P3
  merge.
- **Purpose:** Make the front door show the operating layer.
- **Exact scope:** New `HomeState.tsx` as the default view in
  `gateway/kitty-chat`: What changed (from `/state/changes`), Needs you
  (action cards from `/actions?status=proposed` with approve/reject wired),
  Open loops (untriaged count from triage, proposed actions,
  `needs_jacob` items), Today (calendar/todos — reuse existing panels'
  fetch logic), Capture (existing quick-capture input), chat via existing
  CommandPalette/drawer. Remove fake-data rendering: `LoopWatch` and
  `InsightFeed` either bind to real endpoints or don't render. Keep v2
  tokens; cat state driven by queue + doctor.
- **Files likely touched:** `src/app/page.tsx`, new `src/components/
  HomeState.tsx` + card components, deletions/demotions of
  `DashboardHome.tsx` wiring, UI tests.
- **Files not to touch:** gateway Python (except if a tiny read endpoint gap
  appears — then stop and split a packet), design tokens.
- **Steps:** static layout with live `/state/now` → action cards with
  approve/reject → open-loops bindings → capture wiring → cat state → tests.
- **Acceptance:** `npm test` and `npm run build` green; home renders with
  gateway up and shows honest empty/error states with gateway down; zero
  hardcoded data.
- **Verification:** `cd gateway/kitty-chat && npm test && npm run build`;
  manual walkthrough with `./kitty up`.
- **Risks:** design churn — one review round with Jacob on a screenshot
  before polish; approve-button races — disable on submit, refetch.
- **Rollback:** revert PR; old DashboardHome path restorable from git.
- **Unlocks:** daily use of the whole spine; the habit loop.
- **Too broad if:** it redesigns chat, adds settings UI, or touches mobile
  PWA behavior.
- **Jacob reviews:** the layout (one screenshot approval) and that "Needs
  you" reads clearly enough to approve actions without opening chat.

### P5 — Mail read-only connector (decision-gated)

- **Best executor:** Codex or Claude Code for code; **Jacob himself** for
  account/OAuth setup (credentials are never an agent task).
- **Purpose:** Connect the highest-signal feed, read-only, into signals.
- **Exact scope:** After decision D2 (§16): either Apple Mail via
  AppleScript (mirrors `calendar_integration.py`; fully local) or Gmail API
  read-only scope. New `gateway/connectors/__init__.py` +
  `gateway/connectors/mail.py`: poll for new/flagged messages → signal rows
  (`source="mail"`, dedupe on message id; payload = sender, subject, snippet
  — body stays out of the signal, fetched on demand). Cron-registered poll.
  Triage consumes mail signals like inbox entries. Reply drafting lands
  as `note.draft`-style T1 artifacts only.
- **Files likely touched:** above + `tests/test_mail_connector.py` (mocked
  transport), cron registration, small triage extension.
- **Files not to touch:** action executors (no `email.send` kind — that is
  a later, separate, Jacob-approved packet), auth/secrets handling beyond
  documented env vars.
- **Steps:** transport adapter behind an interface → signal emission +
  dedupe tests → cron poll → triage mapping → doctor check for connector
  health.
- **Acceptance:** mocked-transport tests prove signal shape + dedupe; real
  poll verified manually on Jacob's machine; connector failure surfaces in
  doctor, never silently returns empty.
- **Verification:** `python3.12 -m pytest tests/ -q`; `./kitty doctor --json`
  shows the mail connector check.
- **Risks:** privacy — snippet-only signals, body fetch on explicit demand;
  volume — poll window + dedupe cap the table.
- **Rollback:** disable the cron entry; revert PR; signals rows inert.
- **Unlocks:** the morning brief with real stakes; reply drafts in the
  queue; the connector pattern for GitHub/files.
- **Too broad if:** it sends anything, auto-archives, or adds a second
  provider in the same PR.
- **Jacob reviews:** provider choice, scopes requested, and what fields
  land in the signal payload.

### P6 — Project resume

- **Best executor:** Claude Code; resume-prompt quality reviewed by
  strongest model.
- **Purpose:** Kill resume-archaeology; make continuity real per project.
- **Exact scope:** Migration `009_projects.sql`: `projects(id, name, kind,
  paths_json, status, last_touched, summary, open_questions_json,
  next_actions_json, links_json)`. New `gateway/project_store.py` (CRUD) and
  `gateway/project_resume.py`: `refresh(id)` composes from local git
  (`git log`/branch state for registered paths), journal + chats mentions
  via `memory_graph`, tagged todos, and signals referencing the project;
  `resume(id)` renders the packet (status, changes since last touch,
  open questions, next 3 actions, delegable items). Routes:
  `GET /projects`, `POST /projects`, `POST /projects/{id}/refresh`,
  `GET /projects/{id}/resume`. Seed: the kitty repo itself. UI: project
  cards on HomeState (small P4 extension).
- **Files likely touched:** above + tests for store/resume with a fixture
  git repo.
- **Files not to touch:** `memory_graph` internals (consume its public
  API), `chats_store`/`journal_store` schemas.
- **Steps:** migration + store → git composer with fixture-repo tests →
  memory composer → resume renderer → routes → seed + UI card.
- **Acceptance:** resume for the kitty project returns real branch/PR
  state and recent decisions; refresh is idempotent; non-code project
  (manually registered admin project) renders without git.
- **Verification:** `python3.12 -m pytest tests/ -q`; manual
  `curl /projects/1/resume | jq .`.
- **Risks:** summary drift if LLM-refreshed — keep `summary` last-written-
  wins with the model + timestamp recorded; git ops on missing paths —
  explicit per-source errors in the packet.
- **Rollback:** revert PR; table inert.
- **Unlocks:** P7 delegation from `next_actions`; agent sessions that start
  from Kitty's own resume instead of doc archaeology.
- **Too broad if:** it auto-discovers projects, or tries to parse GitHub
  remotely before the GitHub connector exists (local git only is fine).
- **Jacob reviews:** the resume packet format on the kitty project — does it
  actually answer "where was I?"

### P7 — Delegation packet generator

- **Best executor:** strongest available model authors the template +
  generation prompt; Codex/Claude Code implements the plumbing.
- **Purpose:** Turn an approved action or a project next-action into an
  executor-ready packet — Kitty starts managing its own executors.
- **Exact scope:** New `gateway/delegation.py`: given an action of kind
  `packet.delegate` (new T1 kind — the packet file is a draft artifact),
  render `docs/packets/NNN-slug.md` with title / executor type / purpose /
  exact scope / files touched + not-to-touch / steps / acceptance /
  verification commands / risks / rollback — pre-filled from the source
  action and project resume context. Registry index `docs/packets/README.md`
  with status per packet (draft / handed-off / merged). CLI:
  `./kitty delegate <action-id>`. No process spawning, no API calls to
  executors — the output is the file; Jacob (or a session he starts) carries
  it.
- **Files likely touched:** above + `kitty` launcher subcommand + tests
  (golden-file packet render).
- **Files not to touch:** executor registry tiers, anything that would
  invoke an external agent automatically.
- **Steps:** template → renderer with golden tests → action kind
  registration (T1) → CLI → registry index.
- **Acceptance:** a delegated action produces a packet that this document's
  §15 format would pass; registry updates; nothing executes anywhere.
- **Verification:** `python3.12 -m pytest tests/ -q`; generate one real
  packet and eyeball it.
- **Risks:** packets too vague to execute — golden tests pin required
  sections; mitigated further by generation using project resume context.
- **Rollback:** revert PR; generated markdown is inert.
- **Unlocks:** the full loop — signal → triage → action → approval →
  delegated implementation → PR → state change Kitty reports back.
- **Too broad if:** it spawns agents, posts to GitHub, or manages executor
  sessions.
- **Jacob reviews:** the first generated packet, side by side with a
  hand-written one.

---

## 16. Product decisions for Jacob

1. **Home = state console.** Chat becomes a summonable drawer; the front
   door is What changed / Needs you / Open loops / Today / Capture. This is
   the identity decision — say yes or the rest reshuffles.
2. **Mail connector path.** Apple Mail via AppleScript (fully local, brittle,
   Mac-only — matches calendar) vs. Gmail API read-only (robust, but Google
   OAuth + cloud API in the loop). Read-only either way; sending stays
   off the table until the queue earns trust.
3. **Sign the tier sheet.** Approve `config/action_tiers.json` v1: what's T0
   (todos, local drafts, filing), what's T2 (calendar create), and the T3
   never-list (payments, deletions, secrets, bulk outbound). This document
   proposes defaults; the signature makes them enforceable.

## 17. Architecture decisions to clarify

1. **New stores follow D7:** signals, triage, actions, projects are each
   their own module over `kitty.db` migrations — no storage_router expansion,
   no new database, no event bus. (Proposed: yes; record in DECISIONS.md.)
2. **Connector shape:** all external feeds are cron-polled adapters emitting
   deduped signal rows; no webhooks, no push, no per-connector bespoke
   tables. `web_monitor.py`'s private DB is grandfathered until it migrates.
3. **Privacy boundary in the router:** define data classes (journal, mail
   bodies, health/admin docs = local-only by default; calendar titles,
   todo text = cloud-permitted) and enforce at `llm_client` routing, not by
   convention. This is the decision that keeps "local-first" true once cloud
   models do the drafting.

## 18. What not to build yet

- Voice-native/realtime work beyond what exists.
- Any autonomous outbound: email send, GitHub writes, purchases, browsing
  agents. (Draft-only until the queue has weeks of clean audit history.)
- New memory substrate, typed knowledge graph, MemPalace, event bus.
- Multi-user anything, cloud sync, zero-knowledge vault engineering.
- Native mobile app (PWA + Telegram + Raycast cover reach for now).
- Agent-session orchestration from inside Kitty (P7 stops at the packet
  file on purpose).
- More image-gen features (imagen server is fine; it's a hobby wing, not
  the spine).

## 19. Most dangerous next mistake

**Another lap of internal polish instead of the spine.** The repo's history
shows the pattern: consolidation (Phase B/C), lint/type cleanups, a design
system — each genuinely good, each also a way to feel productive without
making Kitty more useful on a random Tuesday. The soul file names it:
*"beautiful architecture is a great hiding place."* If the next 30 days
produce a cleaner repo and no state endpoint, no triage, and no action queue,
Kitty stays a chatbot.

The runner-up, for balance: wiring outbound actions before the approval
queue exists. That's the fast way to lose the trust the whole product runs
on. Build the queue first (P3), then earn tiers slowly.

## 20. Final revised recommendation

Adopt the operating-layer thesis explicitly (one DECISIONS.md entry), make
the three §16 decisions, and execute P1–P4 in order — they're the spine and
they're all local, reversible, and small. Land the doc cleanup and CI
packets alongside week 1 so remote executors stop inheriting stale context.
Then connect mail read-only (P5), give projects real resume (P6), and close
the loop with delegation packets (P7). At day 30, Kitty opens to "here's
what changed, here's what needs you, here's what I prepared" — with every
action recorded and every boundary enforced in code. That is the real Kitty,
and nothing in the path requires a rewrite, a new database, or a leap of
faith.

---

## Self-review summary

- **What changed after review:** the home surface was reframed from a
  dashboard (panels that display) to an action console (queue-first — the
  "Needs you" strip outranks every visualization); all external-write
  executors were pulled out of the 30-day path except calendar-create, after
  checking the approval infrastructure ships first; email became
  decision-gated rather than assumed-Gmail once the AppleScript-local
  precedent in `calendar_integration.py` was weighed; the fake-data
  loops/insights routes were promoted from a footnote to a week-1 fix because
  they corrode exactly the trust the product depends on; the privacy-boundary
  routing decision (§17.3) was added after noticing the plan quietly sent
  drafting work to cloud models with no stated rule about what content may
  leave the machine.
- **What uncertainty remains:** how much of Jacob's daily contact happens in
  the UI vs. Telegram/Raycast (affects how much P4 matters relative to a
  brief rewrite); whether Gmail's API is acceptable to him at all; the job
  search and benefits/admin workflows appear nowhere in the repo, so their
  shapes are inferred — P6's non-code project test is where that assumption
  gets checked; and whether the local MLX models are strong enough for
  reliable triage classification (P2's stub-model tests keep the seam
  swappable if not).
- **Single highest-leverage next action:** decide §16.1 (home = state
  console) and hand P1 to an executor — every other packet stacks on the
  state spine, and it's a two-day, zero-risk, all-local build.
