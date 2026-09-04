# Swarm 59-Finding Reconciliation — 2026-09-03

**Status:** final reconciliation inventory; **not an execution queue**.

**Product-code baseline:** `origin/main` `35b4a7889824ac285f585567ebd41016caf122af`; rechecked at `6aa79cf543bb1d4875041b1ac0f1e2da5e6a6799`. Intervening merged changes affected coordination, setup/runtime guardrails, and documentation rather than the audited user-facing product code. Re-check current code and runtime before activating any candidate repair.

This ledger recovers all 59 findings from the seven completed specialist subagent transcripts, not only the Top 10 synthesis. It reconciles each against current code/live evidence and assigns a recovery disposition. A disposition preserves evidence; it does **not** activate work. The Lead Integrator chooses work from the running-product outcome and existing ownership.

Statuses:
- **CONFIRMED** — current evidence still supports the underlying problem.
- **SUPERSEDED** — current main already solved or materially changed the claim.
- **REJECTED** — false, technically unsound, or not a product requirement by itself.
- **OUTCOME** — real opportunity/defect, but it belongs inside an active user outcome rather than becoming an independent feature ticket.
- **MEASURE** — plausible; require current runtime/a11y evidence before changing code.

A finding may be both a valid observation and the wrong proposed fix. The disposition preserves the observation while rejecting unsafe or additive solutions.

**Category note:** the source summary records **nine specialist lanes dispatched and seven completed**; the Performance and Adversarial QA lanes failed mid-run and produced no findings. The 59 finding IDs use categories **A, B, C, D, E, F, and I**; G and H therefore do not represent omitted findings. The ledger contains all 59 source findings: A=9, B=7, C=10, D=7, E=7, F=8, I=11.

**Aggregate-label note:** `F-017` in the source summary is the root-cause cluster label for “frontend ignores backend composition,” not a distinct 60th finding. Its constituents are A-002, D-004, E-001, E-002, E-003, E-004, and E-007, all reconciled individually below.

## A — Product coherence

| ID | Current disposition | Recovery domain |
| --- | --- | --- |
| A-001 Web-monitor signal spam | **CONFIRMED / ROOT-CAUSED**: canonical state contained 245 persisted synthetic `example.com` test monitors; their fake `/test*` sources produced the repeated 404 activity. Repair fixture isolation + lifecycle; do not hide with TTL deletion | Automations + product truth |
| A-002 `/chats` full payload for count | **CONFIRMED**, duplicates D-004/E-003 | Home/Chat performance |
| A-003 Image results stranded | **CONFIRMED**: current ImageLab has canonical artifacts but no direct `Use in chat`; Library link/reuse is incomplete | Image Lab |
| A-004 Projects missing from Rail | **REJECTED**: current `RAIL_VIEWS` includes Projects | none |
| A-005 Library/Automations dead ends | **SUPERSEDED/PARTIAL**: both now have actions, but current management/recovery failures remain. Separate salvage PR #811 must not be counted as shipped until independently reconciled/merged | Library / Automations |
| A-006 Home What Changed → Library artifact link | **OUTCOME**: continuity opportunity, not mandatory as a standalone feature | Home/Chat + Library |
| A-007 degraded health from optional semantic memory with no useful recovery | **MEASURE** against current health semantics; canonical doctor still reports semantic memory unavailable when Ollama is down | runtime/settings |
| A-008 hidden secondary surfaces | **OUTCOME**: Research is now in More; Tutor/Journal remain secondary. Discoverability is a product decision, not “expose all” | secondary-capability triage |
| A-009 no cross-surface conversation summary/next-step continuity | **OUTCOME** and consistent with current continuity goal | Home/Chat + Projects |

## B — Interaction/design system

| ID | Current disposition | Recovery domain |
| --- | --- | --- |
| B-001 hover/active states absent | **CONFIRMED/PARTIAL**; shared intentional hover/pressed behavior needed, not a blanket global background rule | precision/a11y |
| B-002 disabled opacity inconsistent | **CONFIRMED** as design-system debt; migrate through primitives | precision/a11y |
| B-003 hardcoded colors bypass themes | **CONFIRMED**; current component tree still has ~93 hardcoded hex/rgba references | precision/a11y |
| B-004 no focus styles | **REJECTED**: current `globals.css` has a global `:focus-visible` outline | none |
| B-005 inconsistent loading patterns | **CONFIRMED** as shared-state/polish debt; fix while migrating active journeys | precision |
| B-006 shared Button barely adopted | **CONFIRMED**: only 7 of 77 component TSX files import it; not a standalone refactor campaign | precision, opportunistic |
| B-007 More menu lacks Escape/outside/backdrop behavior | **CONFIRMED** in current `BottomNav.tsx` | mobile/a11y |

## C — Mobile/accessibility

| ID | Current disposition | Recovery domain |
| --- | --- | --- |
| C-001 Home action tap targets below 44px | **CONFIRMED**: `actionButtonStyle` still has only 5×9 padding and no minHeight | mobile/a11y |
| C-002 InputBar controls 40px desktop | **MEASURE**: 44px is a product touch target, not a universal desktop WCAG failure; test mobile and pointer contexts separately | mobile/a11y |
| C-003 muted text light-theme contrast | **CONFIRMED**: current cosmic/day values remain #7D8699/#8C857A from the swarm baseline | a11y |
| C-004 health status color-only | **CONFIRMED**: `HealthDot` labels the domain but status tone itself is only color | a11y |
| C-005 health-strip changes lack live announcement | **MEASURE** with screen-reader scenario before adding announcements that may become noisy | a11y |
| C-006 More-menu short-viewport overflow | **MEASURE** on short iPhone viewport; current menu is fixed and bounded in width but not height | mobile |
| C-007 single-item orphan health grid | **REJECTED as blocker**; visual polish only if reproduced as materially poor composition | precision |
| C-008 disclosure overflow may clip content | **MEASURE**: current `homeDisclosureStyle` still uses `overflow:hidden`; reproduce actual clipped descendant first | Home/a11y |
| C-009 native details missing explicit aria-expanded | **REJECTED**: native `<details>/<summary>` already exposes expanded state; redundant ARIA is not a goal | none |
| C-010 existing cat-state live region/tab controls | **SUPERSEDED/GOOD EVIDENCE**; preserve | none |

## D — Reliability/edge cases

| ID | Current disposition | Recovery domain |
| --- | --- | --- |
| D-001 signal accumulation/no cleanup | **CONFIRMED**, with synthetic test-monitor persistence now proven as a concrete source; reject silent age-based deletion; use fixture isolation plus dedupe/processed/archive/source lifecycle | Automations/data truth |
| D-002 no bulk signal dismissal | **CONFIRMED** as a usability/recovery need for noisy sources | Automations |
| D-003 approve succeeds/execute fails leaving approved action | **SUPERSEDED**: current action queue atomically claims `executing` and finishes failed/unknown instead of leaving approved | none; preserve regression tests |
| D-004 `/chats` over-fetch | **CONFIRMED**, duplicate A-002/E-003 | Home/Chat performance |
| D-005 duplicate-click lacks server idempotency | **SUPERSEDED**: `_claim_for_execution` atomically guards concurrent execute | none; preserve tests |
| D-006 generic `describeFailure` loses domain recovery | **CONFIRMED** by current Builder screenshot; generic fallback is safe but insufficient for known domain failures | shared failure grammar + active contracts |
| D-007 full `/state` projection for small change check | **MEASURE/LIKELY**; replace only after current request/byte measurements establish waste | performance |

## E — Architecture/performance

| ID | Current disposition | Recovery domain |
| --- | --- | --- |
| E-001 Home many independent calls | **CONFIRMED** in current Home hook usage | Home/Chat performance |
| E-002 NeedsYou five action calls | **CONFIRMED** in `gateway/kitty-chat/src/components/HomeState.tsx` at current lines 1511–1515 | Home/Chat |
| E-003 `/chats` persistence count | **CONFIRMED** at 120s query interval | Home/Chat |
| E-004 mutation hooks duplicated across components | **CONFIRMED as duplication**, but not proof of 3× network refetch | measure/refactor only if useful |
| E-005 86 one-to-one query hooks | **OUTCOME/architecture smell**, not an independent bug; simplify around domain clients while touching active flows | API/query boundary |
| E-006 65/292 endpoint fragmentation | **CONFIRMED**: fresh scan finds 68 Python files under `gateway/routes`, with 299 FastAPI route functions and 300 route decorators (one function has two route aliases); improve through typed/product APIs, not a mass endpoint rewrite | API boundary |
| E-007 single mutation causes three invalidation cascades | **REJECTED pending evidence**: separate hook instances do not cause every observer's callback to run | none unless measured |

## F — AI/agent experience

| ID | Current disposition | Recovery domain |
| --- | --- | --- |
| F-001 memory evidence collapsed by default | **REJECTED as defect** by skeptic; disclosure choice is valid if evidence remains discoverable | none |
| F-002 chat error recovery strong | **GOOD EVIDENCE**; preserve and extend domain-specific recovery rather than replacing it | shared failure grammar |
| F-003 memory evidence suppressed on smalltalk | **CONFIRMED** at current `KittyContext.tsx`; evidence truth should not be decided by local smalltalk heuristic | Home/Chat |
| F-004 requested versus real model unclear | **CONFIRMED/PARTIAL**; picker is detailed but completed turn lacks resolved route | Home/Chat |
| F-005 tools-unavailable invisible | **SUPERSEDED**: current ChatMessage visibly renders `tools unavailable` when header state says unavailable | none |
| F-006 expose system prompt context | **REJECTED as normal-product requirement**; diagnostics may expose bounded context receipts, not raw system prompt internals | developer diagnostics only |
| F-007 Builder job status does not update in Chat | **SUPERSEDED/PARTIAL**: current `useResumeBuilderJob` polls every 10s and card links to Work; remaining Builder clarity belongs to whichever active outcome includes the Builder journey | Builder/Work |
| F-008 actual routed model header dropped | **CONFIRMED**: `X-Kitty-Model-Selected` still not carried into message attribution | Home/Chat |

## I — Hidden leverage

| ID | Current disposition | Recovery domain |
| --- | --- | --- |
| I-001 Magic cross-project connections hidden | **SUPERSEDED/PARTIAL**: Magic is now consumed through `/intelligence`; evaluate usefulness there, no new card by default | capability triage |
| I-002 Life awareness hidden | **SUPERSEDED/PARTIAL**: Life intelligence is also projected through `/intelligence` | capability triage |
| I-003 Council synthesis hidden | **OUTCOME opportunity**: evaluate as internal Chat reasoning tool before exposing UI | capability triage |
| I-004 TELOS hidden | **OUTCOME opportunity**: connect to personal-context/Settings only if editable/useful without file operations | capability triage |
| I-005 longitudinal Patterns hidden | **OUTCOME opportunity**: only surface actionable periodic insight through existing intelligence/brief | capability triage |
| I-006 Research dead view | **SUPERSEDED**: current `ViewRenderer` mounts a real `ResearchView` and More navigation includes Research | secondary-surface acceptance |
| I-007 Dream insight list absent | **OUTCOME opportunity**: integrate into memory/companion only if useful; count-without-access may be confusing | capability triage |
| I-008 Chronicle tips hidden | **OUTCOME opportunity**: avoid another Home banner; integrate only if actionable | capability triage |
| I-009 desktop capture/status/inbox hidden | **OUTCOME/reconciliation**: compare with existing Capture/Library path and consolidate duplicate concepts | capability triage |
| I-010 deadline sweep rich outcome hidden | **OUTCOME**: expose blind spots/confidence only where they change a decision/recovery action | Automations/Home |
| I-011 zombie placeholder views | **SUPERSEDED/PARTIAL**: current ViewRenderer implements Tutor/Journal/Research and aliases several registry entries; stale registry design remains but original “navigate nowhere” claim no longer holds broadly | secondary/navigation cleanup |
