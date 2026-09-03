# Kitty Roadmap — Personal Release-Quality

**Target:** public-release *quality* for Jacob, not a public distribution release
**Active mission:** [`ACTIVE_MISSION.md`](ACTIVE_MISSION.md) — `KITTY-RECOVERY-001`
**Last reconciled:** 2026-09-03
**Planning posture:** living and reviewable; packet existence does not activate execution

This is Kitty's existing roadmap authority, but it is deliberately a **living delivery guide**, not a frozen product contract. It may be reordered, split, or simplified when current runtime evidence changes. Higher-level architecture/decision authority still wins, and only explicitly approved/owned packets become execution work.

The finish line in this roadmap is narrower than an actual public launch: Kitty should feel as complete, trustworthy, coherent, recoverable, responsive, and polished as software we would be comfortable releasing publicly **for Jacob's real use**. Work whose only purpose is distributing Kitty to strangers is parked separately and must not delay this target.

## What “release-quality for Jacob” means

Kitty is at the target when all of the following are true in the **running product**, not just in tests:

1. **Trustworthy runtime.** Status, source/build identity, service health, provider health, and degraded states tell the truth. `unknown` never becomes green by convenience.
2. **One product.** The same Project, Work item, Artifact, deadline, memory, or result keeps its identity and current state across Home, Chat, Work, Projects, Library, Activity, and relevant secondary surfaces.
3. **Every primary surface is complete.** Home, Chat, Work, Projects, Image Lab, Library, Automations, and Settings all support their normal end-to-end jobs in place; no prominent dead controls or read-only dashboard cards survive.
4. **Useful secondary features are real.** Memory controls, capture, brief/push, Tutor, Research, Journal, Agents, tools, todos/monitors, voice, and other exposed capabilities either complete a useful journey or are deliberately hidden/developer-only. No fake product surface remains registered.
5. **Failure is survivable.** Reloads, service restarts, provider failures, interrupted streams/runs, indexing failures, and unavailable integrations preserve recoverable state and explain the next useful action.
6. **Personal data is safe.** Backup/restore is proven, destructive actions retain their approval boundary, uploads are bounded, and phone/Tailnet access does not weaken the local secret boundary.
7. **Fast enough to disappear.** Normal navigation/actions respond immediately, broad polling/request storms are removed, stable layout prevents avoidable jumps, and background work does not make the app feel busy when nothing is happening.
8. **Polished and accessible.** Visual geometry is coherent; phone layout is intentional; primary paths are keyboard usable; focus, contrast, touch targets, reduced motion, empty/loading/error states, and copy are consistently authored.
9. **No known release-blocking defects.** No known P0/P1 product-trust, data-loss, security-boundary, primary-journey, or accessibility blocker remains.
10. **Dogfood evidence exists.** Independent acceptance passes at laptop and iPhone-class widths, then Jacob uses the candidate through normal days without having to fall back to terminal/manual agent coordination for the supported journeys.

## How work enters the roadmap

- A packet/spec is a **candidate**, not an automatic task.
- Before activation, revalidate its finding against fresh `main`, current runtime, Builder, `workspace_global`, and issue #490 ownership.
- Prefer the smallest packet that closes a user-visible outcome or a trust prerequisite.
- Do not bulk-apply the hardening manifests or the ONE KITTY packet set.
- After each phase (or a material change in evidence), review this file and adjust the order. Do not preserve ordering merely because it was written first.

## Phase 0 — Prove the thing we are testing

**Outcome:** when Kitty says a build/service/action is current, healthy, authenticated, bounded, or complete, the evidence supports the claim.

Do first because every later acceptance result depends on it:

- `OK-ACTION-01` — canonical Project/Work object-action contract; integrate only the fresh-main candidate, never the stale Builder base wholesale.
- `KH-RUNTIME-01` — one authoritative runtime/build provenance probe used by status/doctor/runtime reporting.
- `KH-BODY-01` → `KH-IMPORT-01` — actual-byte request bounds and truthful bounded imports.
- `KH-VOICE-01` — authenticated, bounded, multi-turn voice WebSocket semantics.
- `KH-BUILDER-SEC-01` → `KH-BUILDER-SEC-02` — credential-free validation and shell-free new validation commands.
- `KH-JSON-01` → `KH-ERRORS-01/02` — correct HTTP framing and one safe structured user-facing error path.
- `KH-DEPS-PY-01` and `KH-DEPS-WEB-01` — dependency state matches the declared environment and known high-severity production advisories are resolved.
- `KH-REMOTE-01` after runtime truth — authenticated iPhone/Tailnet access without relaxing the loopback proxy secret boundary.

**Exit:** live runtime provenance is trustworthy; the critical request/voice/Builder boundaries are closed; primary acceptance can no longer pass against an unknowable or falsely-green runtime.

## Phase 1 — Make Kitty one product

**Outcome:** objects and actions behave the same way wherever they appear, and Chat/Home/Work/Projects are no longer disconnected applications.

Sequence:

1. `OK-ACTION-02` — shared action renderer/executor.
2. `OK-ACTION-03` + `OK-HOME-01` — Home becomes the prioritized action board.
3. `OK-ACTION-04` — prove the grammar outside Home.
4. `OK-RESPOND-01` — every primary action has truthful press → pending → outcome/recovery feedback.
5. `OK-CONTINUITY-01` — one real object/result chain crosses multiple surfaces without copy/pasting internal IDs.
6. `OK-CHAT-01` → `OK-CHAT-04` — bounded concierge context, typed objects/actions in Chat, and live cross-surface continuity acceptance.

Use the already-authored `KF-*` truth/continuity packets where they close a concrete prerequisite (resume, undo, why-not, timeline, session truth, search, etc.); do not rebuild those capabilities inside ONE KITTY.

**Exit:** Project/Work/Artifact/deadline identity and actions converge across Home, Chat, Work and Projects; the same state transition is not described differently by different screens.

## Phase 2 — Finish every primary surface

**Outcome:** each rail destination is good enough to be the only interface Jacob needs for its job.

- `OK-WORK-01` — Work is a complete operating surface: create/plan/start, monitor, approve when required, retry, unblock, stop/cancel where supported, open evidence/result, and explain why nothing can run.
- `OK-PROJECTS-01` — Projects is the continuity workspace: create/open/resume, current next step, deadlines, related Work/Artifacts, Ask Kitty, and truthful degraded source state.
- `OK-IMAGE-01` — Image Lab supports the real source/character/plan/generate/refine/result loop with identity, provider/route, cost and provenance truth kept understandable.
- `OK-LIBRARY-01` — Library supports ingest/find/open/use/attach/associate and distinguishes saved/indexing/indexed/index-failed/content-unavailable states.
- `OK-AUTOMATIONS-01` — create/edit/enable/disable/run-now/why/retry/history form one truthful automation lifecycle; delivery and duplicate-effect semantics are explicit.
- `OK-SETTINGS-01` — all user-facing configuration actually persists and affects the owning subsystem; integrations/capabilities explain configured/available/degraded state without operator jargon.

Existing packet dependencies include `KT-AUTO-01`, `KT-RESTORE-01`, `KT-BACKUP-UI-01`, `KT-CHAT-TOOLS-01`, `KT-UI-MOUNT-01`, `KF-EASY-01`, `KF-DEFAULT-01`, `KF-MEMORY-01`, `KF-TELOS-01`, `KF-SEARCH-01`, and the precision packets. Revalidate before use rather than assuming old line references still apply.

**Exit:** all eight primary surfaces pass their own running-app happy path, degraded path, reload/restart path where persistence is claimed, desktop, and iPhone-class acceptance.

## Phase 3 — Finish the companion, not just the dashboard

**Outcome:** the features that make Kitty *Kitty* are useful from the product instead of being backend modules or hidden panels.

- `OK-MEMORY-01` — remember/retrieve/pin/correct/explain/forget plus TELOS context are coherent, inspectable, privacy-bounded, and visible where useful without becoming a memory-management chore.
- `OK-TOOLS-01` — safe tools/capabilities are genuinely usable from Chat and discoverable in product language; unavailable capability has one truthful reason/action, not a blank registry.
- `OK-AGENTS-01` — the Global Agent Room/Agents experience supports durable handoff, message/reply/ack, current task/result references, and no fake presence or second execution queue.
- `OK-COMPANION-01` — capture → resurface → brief/push/deadline loop works as one life-first workflow, including the “nothing urgent” and delivery-unavailable cases.
- `OK-SECONDARY-01` — Tutor, Research, Journal, todos/monitors, voice and every other supported secondary destination get one complete useful journey; unsupported/developer-only destinations are hidden rather than left as placeholders.
- `KH-PLUGIN-01` → `KH-CAPABILITY-01` — either make the existing plugin abstraction describe real registered capabilities or truthfully de-emphasize it; one installed/configured/available/launchable health contract feeds product surfaces.

Relevant existing packets (`KF-LIFE-*`, `KF-PATTERNS-01`, `KF-NUDGE-*`, `KF-MAGIC-01`, `KF-TIMELINE-01`, `KF-COUNCIL-01`, `KF-DEADEND-01`, `KT-DEADLINE-01`) remain candidate building blocks, not a mandate to expose every historical experiment.

**Exit:** there is no “finished subsystem in the basement” that Jacob would benefit from while the UI pretends it does not exist, and no surfaced experiment survives merely because code exists.

## Phase 4 — Reliability, recovery, and quiet performance

**Outcome:** normal failures are boring, recoverable, and do not make Kitty noisy or expensive to keep open.

- `KH-PERF-01` — use live events to invalidate state instead of broad 3–5 second polling where the product already has SSE truth.
- `KF-RESUME-01` + `KF-RESUME-BE-01` — interrupted/reloaded Chat keeps durable turn truth.
- `KF-PLACE-01` — drafts, selection/filter/model state that claims continuity survives reload.
- `KF-NOSPIN-01` — loading geometry is stable and avoidable waits are prefetched.
- `KF-OPTIMISTIC-01` — only safely reversible interactions feel immediate; authoritative state still wins.
- `KH-CONT-01/02/03` — finish GAR continuity and retire stale mutable `.claude` continuity without losing cold-start recovery.
- `KT-RESTORE-01` + `KT-BACKUP-UI-01` — real owner-data backup/restore from Kitty, proven against duplicate/loss failure modes.
- `OK-MOBILE-01` — iPhone/Tailnet is a first-class real-use path, including reload, attachment/capture, degraded/offline handling, and secure proxy access.

**Exit:** restart/reload/provider loss/indexing loss/worker interruption have known recovery behavior; idle Kitty is quiet; owner data can be backed up and restored without a terminal.

## Phase 5 — Precision, accessibility, and brand

**Outcome:** Kitty feels authored rather than assembled.

1. `OK-PRECISION-01` establishes shared typography/control/surface/state geometry.
2. Surface migrations: `OK-PRECISION-SHELL`, `OK-PRECISION-HOME-PROJECTS`, `OK-PRECISION-CHAT`, `OK-PRECISION-WORK-ACTIVITY`, `OK-PRECISION-IMAGE`, `OK-PRECISION-LIBRARY-AUTOMATIONS`, `OK-PRECISION-SETTINGS`.
3. `OK-A11Y-01` closes semantic naming, focus order/restore, keyboard paths, contrast/non-color cues, reduced motion, touch targets, zoom/text scaling and screen-reader-critical state announcements.
4. `OK-BRAND-01` adds restrained Kitty illustration/character moments only after the underlying hierarchy works without decoration.

**Exit:** side-by-side primary surfaces share a coherent visual grammar; phone composition is intentional; primary workflows remain understandable with motion/illustration removed and are operable without a pointer.

## Phase 6 — Personal release candidate

**Outcome:** stop building long enough to prove the whole thing.

1. `OK-PASS-01` — ruthless running-product pass. Every finding terminates in FIX, DELETE, explicitly PARK, or REJECT.
2. `OK-RC-01` — final personal release-candidate certification across primary and supported secondary journeys, restart/degraded modes, backup/restore, phone/laptop, and independent review.
3. Jacob dogfoods the candidate through normal use. Bugs found here become bounded repair packets; feature ideas do not automatically reopen scope.

### Release-quality exit gate

The roadmap reaches its target only when:

- every primary surface passes its acceptance matrix;
- every supported secondary feature has a complete journey and every unsupported one is hidden/developer-only;
- no known P0/P1 product-trust, data-loss, security-boundary, primary-journey, or accessibility blocker remains;
- no primary workflow requires a terminal, packet ID, port, env var, raw server error, or manual cross-agent relay;
- desktop and iPhone-class acceptance show no document-level horizontal overflow, clipped/obscured primary control, unhandled console/page error, or mystery click;
- persisted state survives the reload/restart cases it claims to survive;
- backup/restore is independently proven;
- runtime/build provenance is provable on the exact candidate;
- the candidate survives real dogfood without Jacob routinely falling back to manual tools for a supported workflow.

## Public-release-only work — PARKED, not on the active path

These may matter **only if Jacob later decides to distribute Kitty to other people**. They do not count against the personal release-quality target and should not receive active packets now unless they also solve a current Jacob problem.

- generic-user installer/onboarding and removal of Jacob-specific defaults/templates;
- signed/notarized packaged app, installer image, app-store/distribution mechanics;
- license/NOTICE/third-party redistribution review beyond normal dependency hygiene;
- public privacy policy, terms, telemetry/crash-reporting consent and support-data policy;
- multi-user/account/tenant isolation and generic authorization model;
- public update channels, release signing, staged rollout, auto-updater and downgrade compatibility;
- anonymous support bundles, public support workflow, website/marketing/docs for strangers;
- generic cloud deployment, hosted account infrastructure, billing/subscriptions;
- migration tooling whose only purpose is importing another person's existing Kitty installation.

Some underlying qualities remain active when they serve Jacob directly: secure secrets, bounded inputs, backup/restore, trustworthy diagnostics, Tailnet security, dependency hygiene, local recovery, and reproducible startup are **not** public-only chores.

## Explicitly rejected as roadmap strategy

- another frontend foundation;
- a second queue, scheduler, event bus, memory platform, universal-object database, or Builder state machine;
- broad framework rewrites without a measured failure they remove;
- “split every large file” cleanup campaigns with no observable outcome;
- exposing every experimental backend module just because it exists;
- unlimited agent swarms or paid/GPU experiments without a bounded task and budget;
- weakening authentication/loopback boundaries to make phone access convenient;
- treating green unit tests as product acceptance.

## Evidence standard

A roadmap item is complete only when its claim can be reconstructed from supported evidence:

- exact reviewed commit/PR and changed paths;
- deterministic commands and exact results;
- running-app steps for user-visible behavior;
- service-on/service-off or degraded/failure path where relevant;
- reload/restart proof when persistence is claimed;
- desktop and iPhone-class evidence for primary UI work;
- independent review for acceptance-sensitive work;
- explicit remaining limitations;
- no contradiction between success language and missing evidence.
