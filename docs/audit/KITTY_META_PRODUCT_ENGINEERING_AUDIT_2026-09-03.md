# Kitty Meta Product & Engineering Audit — 2026-09-03

**Status:** final audit/reference evidence; **not execution authority** and not a backlog.

**Purpose:** explain why a heavily-built, heavily-tested Kitty still fails ordinary use, and preserve the repair candidates that survive scrutiny without activating them all.

**Evidence baseline:** product-code audit at `origin/main` `35b4a7889824ac285f585567ebd41016caf122af`, live canonical runtime on Jacob's Mac, supported Builder projections, Git/GitHub history, current authority documents, and Jacob's 2026-09-03 dogfood screenshots. Rechecked at `origin/main` `6aa79cf543bb1d4875041b1ac0f1e2da5e6a6799`: intervening merged changes affected coordination, setup/runtime guardrails, and documentation; the audited user-facing product code did not materially change. Any candidate repair still re-checks current `main`, ownership, and runtime evidence before execution.

**Companion artifacts:** `docs/superpowers/specs/2026-09-03-outcome-first-product-delivery-design.md`, `docs/audit/SWARM_59_RECONCILIATION_2026-09-03.md`, `docs/audit/DELIVERY_SYSTEM_REPAIR_CANDIDATES_2026-09-03.md`, and `docs/audit/PRIMARY_PRODUCT_RECOVERY_CANDIDATES_2026-09-03.md`.

## Executive finding

Kitty does not primarily have a programming-language problem. It has an **optimization-target problem**.

The development system became very good at producing bounded diffs, deterministic tests, Builder machinery, governance artifacts, and independently reviewable local changes. Those are useful means. They became the practical definition of progress while the actual product outcome — Jacob completing useful work in Kitty without developer knowledge — remained weakly enforced.

The result is a codebase with substantial real capability and unusually strong local verification machinery, but a product whose integration, lifecycle hygiene, and user-task completion lag far behind its implementation volume.

The correct response is not a rewrite. It is to change what the system considers authoritative evidence of completion, simplify boundaries that accumulated unnecessary complexity, clean product truth, and finish a small number of vertical user journeys before allowing more capability expansion.

## 1. The product goal is clearer than the implementation history suggests

The North Star is stable: Kitty is a local-first personal AI companion that supplies structure, memory, follow-through, and one useful next move; KittyBuilder is supporting infrastructure, not the point of the product.

Jacob's tactical preferences changed during discovery — including native UI versus Open WebUI and how much Builder should expose — but the desired outcome remained recognizable: talk naturally to Kitty, have it know relevant context, let it act or delegate safely, understand what happened, and resume later without operating the machinery manually.

That distinction matters. Iterating on implementation strategy is normal product discovery. A healthy engineering system should absorb those changes while preserving the stable outcome contract. Kitty instead often converted the latest implementation direction into a large body of work before the previous daily-driver loop had been proven.

### Verdict on responsibility

This is not “the app only,” and it is not “Jacob only.” It is a feedback-system failure.

Jacob contributed real pressure toward breadth, parallelism, rapid pivots, and fast merging. The repository history shows corresponding architectural turns and very high change velocity. But the engineering system was supposed to turn that raw product energy into constrained sequencing, reject work that did not advance the North Star, and protect completed outcomes from regression. It often amplified the breadth instead.

The principal-agent/product-lead role described for Kitty was therefore not load-bearing enough. Jacob was repeatedly forced into managing the AI development factory rather than benefiting from the product the factory existed to build.

## 2. The scale of motion exceeded the system's integration capacity

At the audit baseline the repository contains roughly 270k non-archived code/test lines across 1,233 source files. Git records 2,968 commits since 2026-04-23. GitHub history was already above 740 pull requests and 610 merges by the baseline. These are time-bounded scale indicators, not product-health metrics or invariants.

Approximate Git numstat churn over the same period is more than 900k added lines and 460k deleted lines. This is not inherently bad, but it is far beyond the amount of change that one user can meaningfully dogfood between integrations.

The highest-churn product files confirm repeated local reworking rather than stable vertical slices: `HomeState.tsx` has been touched by 50 commits, `gateway.ts` by 99, `builder_loop.py` by 49, and `builder_queue.py` by 31.

There was effectively no sustained release-candidate soak period. Main kept moving while product acceptance was performed against narrow candidate branches and fixtures. That makes it easy for every PR to be locally defensible while the assembled product remains incoherent.

### Process consequence

Kitty needs a WIP limit measured in **activated user outcomes**, not number of branches or agents. One primary outcome should be the default during recovery, but this must not suppress useful curiosity: agents may inspect and root-cause adjacent issues read-only, then capture or hand them to the owning lane. What is constrained is **activation and mutation**, not discovery.

## 3. Packet economics created horizontal fragmentation

Two individually sensible rules conflict at system level.

The product architecture says delivery is an end-to-end chain from intent through verified result and clear UI. But the free-model and packet standards deliberately optimize work for weak unattended workers: one outcome, preferably one file, no discovery or design, deterministic exit-code acceptance, and separate frontend proof because Builder worktrees lack the Node toolchain.

The active packet standard goes further: when a sentence contains multiple outcomes, split it; a frontend-only packet is interactive; and splitting UI from backend is “usually the right call.” Historically it records 167 Builder runs with only one completed run at the time the standard was written, illustrating how much effort has gone into making atomic execution machinery reliable.

Those rules are appropriate **inside an already-designed vertical slice**. They are harmful when used to define the product itself. The system repeatedly decomposed a user outcome into backend, frontend, projection, polish, and acceptance fragments and then allowed each fragment to acquire its own definition of done.

### Repair

Keep atomic packets as execution units beneath a thin active-outcome contract. Do **not** pre-create six Product Contracts or build a second planning system. The currently active outcome alone needs enough durable authority that child packets cannot redefine success downward; the mechanism must earn its maintenance cost on the first repaired outcome before expanding.

## 4. “Running-app acceptance” is weaker than its name

The written Product Acceptance policy is excellent: a feature is not accepted because a route exists or component renders; an independent reviewer must complete the intended task in the running product. The enforcement and test architecture do not fully implement that policy.

The PR scope classifier defines `user_facing` only as changes beneath `gateway/kitty-chat/src` or `public`. A backend-only change that alters the behavior, lifecycle, provenance, cost, or failure semantics of a user workflow does not trigger the same product-acceptance requirement.

The standard Playwright configuration runs a real production Next.js build, but most smoke specs route-stub the Gateway. The mobile “dogfood” spec explicitly says it runs without a live Gateway. The hermetic suite adds a real FastAPI process but uses a fake LiteLLM and only a small selected test set. These are valuable integration tests, but they are not the same thing as completing the user task against Jacob's actual canonical state and dependencies.

That gap explains how a Builder view can be “verified” while the real Builder screen errors, how an Image Lab can pass offline/fail-closed acceptance while Jacob cannot bind the intended character and generate, and how Library rendering tests can pass while the canonical Library is full of stale acceptance debris.

### Repair

Use four distinct names and never substitute one for another: **mechanical/component proof**, **hermetic integration proof**, **exact-candidate isolated proof**, and **canonical dogfood proof**. Live-provider proof is an additional property when the outcome depends on a real provider. Canonical proof is required for claims about Jacob's actual running workflow, not as a ritual on every PR.

## 5. Product truth is contaminated by lifecycle failures

This is not merely presentation debt. Canonical product state currently contains data that should not be presented as ordinary user truth.

Projects lists five records as active, including `Treatment decision by Aug 18` and `Clean and organize room`. `benefits-admin` is seeded automatically by backend code. The backend supports reversible archival, but the Projects UI does not provide a coherent lifecycle-management path. The object model has allowed tasks/decisions/deadlines and durable projects to blur together.

Library contains 140 artifacts in the canonical store. A later exact read-only reconciliation proved that 132 point at vanished pytest temporary paths; this is synthetic acceptance/test contamination, not 132 lost user files. The artifact record already contains provenance fields (`created_by`, `source_ref`, capture type, ingestion error), but normal Library presentation does not sufficiently distinguish real files, missing backing files, synthetic history, and indexing state.

Automations/activity had the same class of contamination: 245 persisted `example.com`/test monitors generated repeated 404 activity. The important defect is not merely noisy copy; test fixtures survived into canonical product state and were faithfully rendered as real work.

Builder shows the same lifecycle accumulation at a larger scale: the supported projections currently report 83 initiatives — 57 paused, 11 active, 11 completed, four failed — and 342 queue tasks, of which 264 are cancelled, 61 done, 10 queued, six blocked, and one failed.

### Repair

Before surface redesign, establish lifecycle truth and product visibility rules. Historical, cancelled, test, diagnostic, and operator evidence must remain durable where required but must not compete with active user objects in normal views. Tests and acceptance rigs must be structurally unable to write canonical personal stores.

## 6. Builder became a second product instead of invisible leverage

The North Star explicitly says Builder work is overhead unless it moves Jacob's life forward. The repository nevertheless contains about 24.6k lines across 35 Builder-named Python files (33 top-level `gateway/builder*.py` files plus the Builder model and route modules), hundreds of Builder-focused commits, a multi-pane cockpit, queue/recovery/supervisor machinery, extensive tests, and its own large body of governance.

Much of that engineering is real and valuable. The inversion is in presentation and prioritization: the control plane became something Jacob has to understand.

The repo already implements conversation → prepared Builder proposal → explicit approval → durable job → Work handoff. But the dedicated Builder experience remains an operator cockpit. A direct “Ask Builder” form was briefly added to Work and then removed in main commit `7c5b1438` because it required developer concepts such as `allowed_paths`; nothing replaced it with the intended ordinary-language experience.

There is also a mechanical delivery cause: isolated Builder worktrees inherit a usable Python validation environment but not a local Node dependency tree. The packet standard institutionalized frontend proof as a separate lane. That makes backend/frontend fragmentation cheaper than vertical completion and should be treated as an execution-environment defect, not merely a planning preference.

The current runtime manifest exposes the boundary problem numerically. A local composition at audit time was about 1.18 MB; approximately 1.176 MB was `execution.builder`. The frontend polls this projection every 15 seconds when idle and every five seconds with an active Builder run. Product runtime truth is physically dominated by execution-control detail.

### Repair

Keep Builder's durable execution core. Split lightweight product/runtime summary from paged/event-driven Builder detail. Make the default Builder surface an intent-and-governance experience; move packet trees, leases, raw attempts, and internal IDs behind an Advanced/Diagnostics disclosure.

## 7. Technology-stack verdict

| Layer | Verdict | Reason |
| --- | --- | --- |
| Python 3.12 | **KEEP** | Best fit for AI/provider/local automation ecosystem; rewrite cost would dwarf benefit. The problem is weak contracts, not the language itself. |
| FastAPI + Pydantic | **KEEP, use properly** | Appropriate local API boundary. Public routes need typed response contracts instead of pervasive dict-shaped payloads. |
| React + TypeScript | **KEEP** | Strong fit for one responsive Mac/iPhone web surface and rapid UI iteration. |
| Next.js 16 | **KEEP during recovery; benchmark later** | Kitty uses little SSR/server rendering; Next mainly supplies the app host and authenticated loopback proxy. It adds a Node process and proxy/bind complexity, but a rewrite now would reset product progress. After stabilization compare current Next against a simpler Vite/static SPA served through the Gateway. |
| TanStack Query | **KEEP, centralize** | Good server-state primitive; current problem is query fan-out and duplicated consumption, not the library. |
| SQLite/WAL | **STRONGLY KEEP** | Excellent authoritative store for single-user local-first Kitty. Simplify around it rather than replace it. |
| LiteLLM | **KEEP behind a narrow boundary** | Useful provider abstraction; provider/model details must not leak into product logic. |
| ChromaDB + mem0 + JSONL + MemoryGraph/other stores | **CLASSIFY / RECONCILE LIFECYCLE** | Multiple stores can be appropriate. The defect is unclear authority, rebuildability, health, and user-visible lifecycle. Keep SQLite/filesystem as durable authority where applicable and make semantic indexes explicitly derived/rebuildable before considering consolidation. |
| SwiftUI/React Native/Tauri rewrite | **DO NOT DO NOW** | Native rewrites do not solve outcome authority, stale data, lifecycle, or acceptance. Packaging can be revisited after the web product is trustworthy. |

## 8. The actual language-level problem is contract looseness

Python's flexibility has been used at too many architectural boundaries. A fresh AST scan finds 299 FastAPI route functions under `gateway/routes`, represented by 300 route decorators because `morning_brief` has two `@router.get` aliases. Only three route decorators declare `response_model`; 140 route functions have no return annotation, 152 use an explicit `dict`-shaped return annotation, and the remaining seven use another explicit return annotation.

Across `gateway/`, there are roughly 1,588 references to `Any` and 1,768 dict-shaped signature/return patterns. Mypy is intentionally lenient (`check_untyped_defs = false`) for most Gateway code and excludes tests; only three modules are currently ratcheted to body-level checking.

The frontend compensates by maintaining a 2,659-line `gateway.ts` with 127 exported hand-written interfaces/types. The repository documentation itself warns that these shapes drift and describes generated OpenAPI TypeScript types as the solution — but current main has no generated schema and no production import of one. Prior implementations exist on non-main/salvage history, not as a load-bearing current contract.

### Repair

Do not migrate languages. Establish a typed boundary: Pydantic request/response models for product APIs, deterministic OpenAPI generation in CI, generated TypeScript consumed by the frontend, and a ratchet preventing new untyped public routes. Internal exploratory Python can remain dynamic where that buys speed.

## 9. Persistence diversity is not the defect; lifecycle ambiguity is

The current Gateway touches SQLite from 64 Python files, JSONL from 28, ChromaDB from 10, mem0 from six, and performs direct filesystem writes from dozens of modules. The main SQLite schema already spans roughly 55 tables.

This breadth reflects real feature growth. Multiple persistence technologies are not inherently wrong; the operational defect is that “saved,” “indexed,” “remembered,” “available,” and “current” do not have sufficiently explicit authority and lifecycle semantics. Canonical Library data demonstrates the failure mode: a durable registry row can outlive its backing file or indexing attempt while the product still presents a misleadingly simple state.

Memory retrieval fans out across projects, explicit memory, semantic memory, knowledge, journal, traces, todos, inbox, signals, chat messages, and optional backends. Partial-failure handling is thoughtful, but the product pays complexity for every additional adapter.

### Repair

Define three lifecycle classes: **authoritative durable state**, **durable user files/artifacts**, and **derived indexes/caches**. Every store must declare which class it serves, how health is observed, and what happens when it is unavailable. Derived systems must be rebuildable and may never make authoritative content appear absent. Consolidate technologies only when measured operational cost justifies it.

## 10. Preserve initiative; constrain activation

This audit produced a live example of the coordination problem. While reviewing Product Reality, an agent noticed genuine Daily Driver Library/Chat defects and proactively investigated them. That initiative produced useful evidence and a tested salvage PR. The error was silently converting the discovery into a new implementation assignment after another Lead Integrator had established sequencing authority.

The correct repair is **not** “stay in your lane and stop looking.” Agents should be encouraged to notice, reproduce, root-cause, and communicate adjacent problems. Read-only discovery does not require taking implementation ownership. Before mutation, the agent must reconcile the finding with the active outcome and existing owner. If it directly serves the current outcome and has no conflicting owner, it may be absorbed; otherwise it is handed off or parked. Security/data-loss/P0 findings may preempt through the existing escalation path.

The principle is: **look outside your lane constantly; do not steal another lane silently. Constrain activation, not curiosity.**

## 11. Root-cause ranking

### P0 — Delivery system

1. **Outcome authority is not load-bearing.** Packet/PR completion can occur while the parent user task remains incomplete.
2. **Canonical product proof is optional or misclassified.** Backend workflow changes can evade acceptance; most browser proof uses stubs.
3. **Atomic-worker economics define product decomposition.** The system optimizes for what weak agents can prove instead of using weak agents only after a strong vertical design exists.
4. **Change velocity exceeds dogfood bandwidth.** Main changes faster than one human can establish stable product truth.
5. **Builder/agent infrastructure became a recursive optimization target.** The machine built to build Kitty competes with Kitty for attention.

### P1 — Product architecture

6. **Lifecycle/provenance rules are incomplete.** Stale Projects, test-contaminated Library, and historical Builder state leak into normal product views.
7. **Conceptual boundaries are not physical enough.** Builder is a large subsystem inside the Gateway package and dominates runtime projection payloads.
8. **API contracts are weakly typed across Python/TypeScript.** Hand-maintained shapes encourage silent drift.
9. **Frontend consumption is fragmented.** Large view modules and many independent queries turn existing backend composition into duplicated network/state behavior.
10. **Persistence/index lifecycle is ambiguous.** Derived systems are too visible in ordinary product behavior; technology diversity itself is not the defect.

## 12. What to stop immediately

Until the recovery gates pass:

- Do not add new primary product destinations.
- Do not add a hidden-capability card merely because an endpoint exists.
- Do not add another agent/orchestration layer unless it directly unblocks the current active user outcome.
- Do not start a language or frontend-framework rewrite during recovery.
- Do not perform broad cleanup that cannot name a user or reliability outcome.
- Do not create a family of Product Contracts before one active outcome proves the mechanism useful.
- Do not describe fixture-only evidence as canonical dogfood.
- Do not let acceptance or test runs write Jacob's canonical application data.
- Do not show historical Builder state as current user work solely because it remains durable.
- Do not add another semantic-memory/index system without an explicit consolidation decision.

## 13. What to do next

1. Let the Lead Integrator maintain the exact running candidate and consolidate the failure evidence already gathered from Jacob's screenshots, live inspection, and current runtime. This is a repeatable baseline, not a demand that Jacob spend a week using an unusable app.
2. Follow the active Mission/ROADMAP sequence unless fresh evidence justifies an explicit authority change. At this audit closeout, `docs/ACTIVE_MISSION.md` selects **BUILDER-001** next; this audit does not override that decision or silently choose a different surface.
3. Repair the selected outcome vertically, using existing coordination and the smallest delivery guardrails that prevent a demonstrated failure. If runtime evidence invalidates the selected outcome or ordering, reconcile that through the Mission/ROADMAP authority instead of switching lanes ad hoc.
4. Re-run the same real workflow that failed. A green implementation without the running result remains incomplete.
5. After the first outcome, review the methodology itself. Keep only rules that demonstrably prevented premature completion, collision, test-data contamination, or repeated manual checking.
6. Continue product recovery from observed failures; architecture, performance, accessibility, security, and hidden-capability work attach to active journeys unless separately proven urgent.

The companion candidate inventories preserve likely repairs without becoming another executable master program.

## Bottom line

Kitty's core product idea remains strong and the majority of its foundational technology choices remain defensible. The dominant failure was allowing enormous AI implementation throughput to outrun product integration and human acceptance. The system repeatedly learned the right lesson in prose, then failed to convert that lesson into an invariant.

The recovery strategy is therefore: **preserve engines, reduce machinery, repair truth, finish one vertical outcome at a time, keep proactive discovery alive, and make running user-task completion outrank implementation claims.**
