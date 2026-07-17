# Kitty Blueprint — 2026-07-11

Product direction, written by Fable from the
`docs/fable-context` bundle, the Codex audit, the verified visual references,
and the live system state observed on 2026-07-11. Durable decisions extracted
here live in `docs/DECISIONS.md`. ADR 0017 supersedes this document's former
read-only Kitty/Builder boundary; current status comes from
`docs/PROJECT_STATUS.md`, not the dated doctor result above.

---

## 1. What Kitty is

Kitty is Jacob's local-first companion whose defining experience is the
**resume loop**:

> Open Kitty at any time and within five seconds know: what happened while you
> were away, what's next, and what needs you. Continue any of it in one tap.

That is the product. Chat, memory, capture, projects, briefs, images — all of
it serves the resume loop. Competing AI tools are stateless request/response
machines; Kitty's edge is *continuity + honest state + delegation*. Every
feature is judged by: does it make resuming easier, or is it a dashboard tile?

**Not** the product: an engineering dashboard, a second Grafana, a place to
watch worker logs scroll.

## 2. The two systems

| | Kitty (product) | KittyBuilder (control plane) |
|---|---|---|
| Owns | conversation, product intent, selective context, mission compilation, chat, memory, capture, projects, tasks, briefs, tools, images, continuity, UI | accepted missions, initiatives, packets, attempts, worktrees, worker/model routing, verification, recovery, evidence, publish |
| Truth store | `data/` (chat DB, memory, journal) | builder queue DB + run manifests |
| Contract between them | Submits only a versioned, validated, authorized Mission through a supported interface; reads structured results/evidence | Accepts the governed Mission and returns versioned execution state and evidence; never owns Kitty personal stores or `.env` |
| Fails independently? | Kitty must be fully usable with Builder offline | Builder runs headless; Kitty UI is optional over it |

Shared: versioned mission/result identifiers, the FastAPI gateway process, the
risk-tier vocabulary (T0/T1/T2), and evidence contracts. No implicit shared
state. Kitty and its UI use supported Builder interfaces, never Builder tables.
The Mission write boundary is defined but not autonomously enabled.

**Orca is an adapter, not a system.** It transports tasks to worker terminals
and reports back. Durable task state lives only in the Builder queue
(`./kitty builder queue`); if Orca dies mid-task, the queue lease expires and
the packet is retryable. Orca must never be the only place a task exists.

## 3. Contracts (the stable surface)

1. **Gateway HTTP API** — one route owner per `(method, path)`; enforced by
   `tests/test_route_contracts.py` (landed 2026-07-11). Response shapes are
   frontend contracts; changing one requires a companion frontend change.
2. **Builder run manifest** — every attempt records: task ID, base SHA,
   worktree, model, changed files, tests run, transcript path, verdict,
   structured JSON (never parsed from log tails).
3. **Failure semantics** — failures are `failed`/`interrupted`, never
   `completed`; empty is an explicit empty state, never a swallowed exception.
   This is the trust contract for both systems.
4. **Risk tiers** — T0/T1: free workers in isolated worktrees, no secrets, no
   push. T2 (security, auth, persistence, concurrency, destructive): Codex or
   Jacob only. Publish is always operator-gated.
5. **Mission contract** — approved intent, selected/missing context,
   assumptions, authority, budgets, acceptance evidence, and base identity cross
   into Builder as one versioned object (ADR 0017).

Everything else — internal module layout, storage engines, route module
grouping — is internal and may churn freely.

## 4. UX direction (verified visuals)

From the corrected references in `docs/fable-context/assets/`:

- **Theme**: the dark "cosmic" look — deep navy space background, warm orange
  accent, card grid. The cosmic theme already exists in `globals.css` and its
  cascade bug is fixed; it becomes the default identity, with day mode kept.
- **Mascot**: hand-drawn white **line-art doodle cats** (starry-eyed cat-head
  logo, rain-cloud cat, standing sketch cat). Not rendered/3D. Usage: logo mark,
  empty states (rain-cloud cat for errors/offline), and moments of delight —
  never blocking content. SVG line art, trivially themeable.
- **Home** is the resume loop, three zones: **What's Next** (one suggested
  action, not ten), **Needs You** (escalations, expired tokens, T2 approvals,
  deadline rails), **While You Were Away** (brief, capture resurfacing,
  delegated-work results). Everything continuable into chat with context
  pre-loaded.
- **Chat is the spine**, not a tab: every card, project, and artifact offers
  "continue in chat" carrying its context.
- Mobile/PWA: the resume loop is exactly what a phone glance wants. Home +
  chat first; heavy surfaces (Image Lab, Builder) can stay desktop-first.

## 5. Honesty ledger — fake vs real today

Real and verified: gateway/LiteLLM services, chat + saved chats, todos/Today
error honesty, builder S1–S5 queue path (340 tests), verifier (false-green
fixed), route contracts, personality/feedback endpoints (tests, not browser).

Fake, broken, or unproven — must not be presented as working:

| Thing | State | Decision |
|---|---|---|
| Memory consolidation on session close | no-op | make it real (small: write a consolidation record) — product lane P2 |
| Insights/dream store | effectively empty no-op | **disable visibly** ("not built yet") until consolidation is real; don't fake |
| Gmail | token expired | Needs You card, one-tap reauth guidance |
| Telegram | disabled | postpone; remove from UI |
| Chroma | zero collections | seed from real capture flow, not synthetic data |
| Image gen | ComfyUI not running | keep the truthful status card (already done); slice waits for env |
| Browser-verified UI | never done | this session starts it; becomes a release gate |
| agent_runner/task_runner completion states | can report false `completed` | T2 — escalated to Codex/Jacob (Card B) |

## 6. What survives, what changes, what dies

**Survives**: gateway + Next.js UI shape, builder queue/worktree/publish path,
LiteLLM routing, memory_graph read seam, risk tiers, operator-gated publish,
cosmic theme, doodle mascot direction.

**Changes**: Home becomes the resume loop; failure semantics swept fail-loud
(Card C); docs reconciled to code (Card H); route surface frozen — no new
route module without deleting one.

**Dies / postponed**: Honcho mirror (not wired, stays out), Telegram (off),
fal (already retired), dream/insights UI until real, speculative expert-pack
expansion. Anything that exists only because a past session built it and no
user loop touches it is a deletion candidate — complexity is not sacred.

## 7. Execution lanes

### Trust lane (make the truth trustworthy)
1. ✅ Verifier false-green, route contracts, two fail-loud paths (committed `569608b`)
2. **Browser QA smoke** — live pass now, then Playwright suite (Card F) as CI gate
3. Card B escalation note for Codex/Jacob (agent/task runner states) — T2
4. Card C fail-loud sweep (T1, free-worker sized: one module per packet)
5. Card A security (LAN bind + SSRF) — T2, escalated, not started per rule
6. Cards G/H: CI alignment, doc reconciliation (T1, delegable)

### Product lane (vertical slices, in order)
1. **P1 Home resume loop** — What's Next / Needs You / While You Were Away on
   real endpoints (next_step, deadlines, state changes, doctor warnings as
   Needs You cards). Browser-verified.
2. **P2 Real continuity** — session close writes a consolidation record;
   next session's What's Next reads it (closes Card D honestly).
3. **P3 Capture → resurfacing** — capture feeds Chroma; resurfaced items
   appear in While You Were Away.
4. **P4 Mascot + cosmic identity** — SVG line-art cats in logo/empty states,
   cosmic default.
5. **P5 Governed delegation** — Kitty compiles an approval-ready Mission,
   submits it only through the authorized boundary, and reads Builder's bounded
   result/evidence projection. The shipped Builder UI remains read-only until
   mutation endpoints enforce the same policy and fencing as the CLI.
6. **P6 Mobile/PWA pass**, then **P7 Image Lab** once ComfyUI is actually up.

Each slice ships browser-verified or it isn't shipped. Free workers get
P-slices only when bounded (P4 SVG work, P3 backend), always T0/T1 cards with
the bundle's standing rules (isolated worktree, no secrets, structured JSON
handoff, independent review).

## 8. Continuity model

- `.claude/STATE.md` — one current structured checkpoint, never an append-only ledger.
- `.claude/HANDOFF.md` — one current resumable handoff, explicitly invalidated when stale.
- Builder queue — durable machine state for delegated work.
- Git and archives own history; active checkpoint files do not preserve old checkpoints.
- Kitty-the-product mirrors this for Jacob: session close → consolidation
  record → next session's What's Next. The engineering discipline and the
  product feature are the same idea; P2 makes them literally share a shape.
