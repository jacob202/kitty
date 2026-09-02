# ONE KITTY — Theft Ledger Scout Report

**Date:** 2026-09-02
**Scope:** Read-only audit of `gateway/` and `gateway/kitty-chat/src/` against `ONE_KITTY_THEFT_LEDGER_2026-08-31.md`

---

## Executive Summary

Wave 1 (OK-ACTION-01/02 canonical action grammar) can **reuse** today:
- The ActionQueue (propose → approve/reject → execute with T0/T1/T2 tiers) and its approval UI (ActionCard, NeedsYou approve/run buttons);
- The `next_action` / `rowAction` projection in WorkView that already computes canonical actions per work item;
- The context reference system (`@`-mention + HTML markers) for Chat-to-object binding.

Wave 1 **must build**:
- A general-purpose "canonical object declares its primary + contextual actions" framework (currently actions are hardcoded per work-item type, not declared by each object);
- A discoverable contextual action menu (no sidebar, popover, or right-click menu exists anywhere);
- Enter-as-primary-action on selected objects (currently Enter only sends chat);
- Action grouping by user purpose (currently grouped by workflow state, not intent);
- Keyboard shortcut visibility through menus (shortcuts are hardcoded in CommandPalette only).

---

## 1. Raycast — actions belong to the selected object

| # | Steal specifically | Status | Evidence | Wave destination | Gap note |
|---|-------------------|--------|----------|-----------------|----------|
| 1 | every canonical Kitty object can declare a primary action and contextual secondary actions | **PARTIAL** | `WorkView.tsx:279-305` (`rowAction` per work item), `ActionCard.tsx:27-31` (approve/execute per action) | Wave 1 Action Grammar, Wave 2 Chat Concierge | Only Work/packet items have mapped actions; there is no `declare_primary_action` protocol for Projects, Artifacts, Deadlines, or other canonical objects |
| 2 | `Enter`/tap invokes the obvious primary action where safe | **PARTIAL** | `InputBar.tsx:213-217` (Enter sends chat), `WorkView.tsx:425,466,492` (primaryActionStyle buttons exist but not Enter-triggered) | Wave 1 Action Grammar | Enter triggers chat send, not the primary action of the currently selected/focused object; work items require clicking a styled button |
| 3 | a discoverable action menu exposes the rest | **MISSING** | No contextual action menu found in any component | Wave 1 Action Grammar, Wave 2 Chat Concierge | No sidebar, popover, dropdown, or right-click menu exists for any object's secondary actions — actions are only exposed via hardcoded buttons or the CommandPalette |
| 4 | actions are grouped by user purpose, not backend route | **PARTIAL** | `WorkView.tsx:16-19` (groups: `needs-you`, `in-progress`, `completed`), `ActionCard.tsx:46` (shows `item.kind` as eyebrow) | Wave 1 Action Grammar | Grouping is by lifecycle/state, not user intent; no semantic grouping like "review", "configure", "share", "investigate" |
| 5 | keyboard shortcuts can be taught through the visible menus | **MISSING** | `CommandPalette.tsx:209,374-390` (hardcoded `shortcut="N"`, kbd style) | Wave 1 Action Grammar | Shortcuts exist only in the CommandPalette (and only for "new chat"); no visible shortcut hints on any action button or menu item; no progressive teaching mechanism |
| 6 | Chat can operate against the same object/action definitions rather than inventing prose instructions | **MISSING** | `context-references.ts:1-31` (Chat references objects but not their actions), `action_queue.py:29-36` (propose takes `kind`/`title` but no object binding grammar) | Wave 2 Chat Concierge | Chat has context references (projects/artifacts/chats) but no mechanism to resolve an object's available actions and operate against them; proposals are prose-defined |
| 7 | consequential Chat tool use keeps explicit approval boundaries | **EXISTS** | `action_queue.py:11-26` (T2 requires explicit approval), `ActionCard.tsx:68` (approve button), `action_grants.py` (user-defined grants) | Wave 2 Chat Concierge | — |

## 2. Linear — contextual actions and invisible precision

| # | Steal specifically | Status | Evidence | Wave destination | Gap note |
|---|-------------------|--------|----------|-----------------|----------|
| 1 | contextual menus should act on the underlying object, not only the notification/card wrapper | **MISSING** | No contextual menus found anywhere in the codebase | Wave 3 Home Action Board | All actions are flat buttons on card wrappers; no contextual menu exists that would let you act on the underlying object directly |
| 2 | Home attention items should expose the underlying object's meaningful action | **PARTIAL** | `HomeState.tsx:1507-1586` (NeedsYou with approve/run), `HomeState.tsx:2019-2020` (HomeIntelligence projection) | Wave 3 Home Action Board | Action queue items have approve/run; but deadlines, triage entries, and signals in Home are static cards with no executable action |
| 3 | current surface/selection affects action ranking | **MISSING** | `CommandPalette.tsx:19-30` (static view command list), no ranking based on current view | Wave 3 Home Action Board, Wave 5 Precision | CommandPalette shows the same commands regardless of context; no view-aware or selection-aware action ordering |
| 4 | visible shortcut hints progressively teach faster operation | **MISSING** | `CommandPalette.tsx:390` (kbd tag), only one shortcut in codebase | Wave 3 Home Action Board, Wave 5 Precision | No progressive reveal of shortcuts; no hints next to action buttons; shortcuts are invisible to new users |
| 5 | engineer micro-interactions when they remove repeated friction | **PARTIAL** | `globals.css:37-38` (`:focus-visible`, `--color-focus-ring`), `globals.css:43` (reduced-motion), `Button.tsx`, `Dialog.tsx` | Wave 5 Precision, Wave 8 Ruthless Pass | Design tokens and some accessibility exist, but most components use inline styles (no component abstraction), loading geometry is unstable, and micro-interactions like menu placement/focus restore are absent |
| 6 | attention items can be snoozed/deferred only when Kitty has a truthful model for doing so | **PARTIAL** | `InsightReturnCard.tsx:49-50,93,97` (snooze with `snoozeUntil`), `deadline_store.py` (deadline model) | Wave 3 Home Action Board | Insight loop items have snooze; but Needs You items (proposed/approved actions) lack deferral, and general attention items have no schedule/reminder model backing |

## 3. Anthropic / Claude — brand character as punctuation

| # | Steal specifically | Status | Evidence | Wave destination | Gap note |
|---|-------------------|--------|----------|-----------------|----------|
| 1 | define a canonical illustration language rather than one-off doodles | **PARTIAL** | `CrayonCat.tsx:1-281` (consistent SVG "crayon" style with wobble filters), `cat-assets/state-idle.svg`, `state-working.svg`, `state-done.svg`, `state-broke.svg` | Wave 6 Kitty Brand Character | The hand-drawn "crayon" style is consistent across CrayonCat and state SVGs, but kid-cat.svg and 8bit-*.svg are divergent styles; no canonical illustration language document exists |
| 2 | create a small state family: hello, thinking, working, waiting, found something, success, empty, offline/sleeping, creative, Builder | **PARTIAL** | `CrayonCat.tsx:5` (CatState: `idle`/`working`/`done`/`broke` ≈ 4 of 10 requested states), `cat-assets/` adds `state-idle`, `state-working`, `state-done`, `state-broke`, `8bit-sleep` | Wave 6 Kitty Brand Character | Current state family covers idle, working, done, broke (40% of requested); missing hello, waiting, found something, success, empty, offline/sleeping, creative, Builder states with corresponding illustration |
| 3 | use illustration in high-salience emotional/state moments | **EXISTS** | `CrayonCat.tsx:16-36` (CatCorner fixed bottom-right), `CrayonCat.tsx:40-71` (CatMark in rail/header), `HomeState.tsx:953` (KidCatDoodle in empty state) | Wave 6 Kitty Brand Character | — |
| 4 | keep working surfaces mostly typographic and structural | **EXISTS** | All primary surfaces (Home, Work, Chat, Projects, Settings) are typography/text-driven with minimal mascot presence | Wave 6 Kitty Brand Character | — |
| 5 | use the same spacing/type/color system around illustrations so brand and UI feel related | **PARTIAL** | `globals.css:118-142` (font family, spacing, radius tokens), `CrayonCat.tsx:7-11` (EYE_COLORS uses `--cat-green`, `--c-yellow`, `--c-green`, `--c-red` which are not part of the semantic token system) | Wave 6 Kitty Brand Character | Illustration colors use their own variables (--cat-ginger, --cat-pink, --cat-green) separate from the semantic design tokens; illustration and UI palettes are not mapped to the same system |

## 4. Raycast AI — Chat as an action-capable connective layer

| # | Steal specifically | Status | Evidence | Wave destination | Gap note |
|---|-------------------|--------|----------|-----------------|----------|
| 1 | Chat gets a bounded catalog/projection of available Kitty context and actions | **PARTIAL** | `capability_report.py:1-180` (startup capability report), `activity_projection.py:218` (build_activity_projection), `context-references.ts:1-31` (context reference markers) | Wave 2 Chat Concierge | The capability report is a startup log, not a runtime API Chat can query; no combined "available context + actions" catalog endpoint exists |
| 2 | explicit user references outrank inferred relevance | **PARTIAL** | `InputBar.tsx:165-186` (@-mention context picker), `context-references.ts:13-24` (appendContextMarkers adds explicit references) | Wave 2 Chat Concierge | Explicit @-references are appended as markers but server-side relevance ranking (explicit vs inferred) is not visible; `context_assembler.py` merges sources without an explicit ranking signal |
| 3 | active Project/context influences ranking | **PARTIAL** | `context-references.ts:1` (project kind), `context_assembler.py` (assembles active project context) | Wave 2 Chat Concierge | Active project context is assembled, but "influences ranking" is implicit — no exposed ranking/priority signal in the assembled context bundle |
| 4 | Chat may combine multiple domains in one answer/action plan | **EXISTS** | `InputBar.tsx:53-55` (multiple contextCandidates), `context-references.ts:1` (project/artifact/chat kinds), `activity_projection.py` (multi-source activity) | Wave 2 Chat Concierge | — |
| 5 | tool/action execution stays visible and approval-aware | **EXISTS** | `ToolCallBlock.tsx:19-48` (tool call list in chat), `ToolCallCard.tsx:23` (tool state: running/done/failed), `ActionCard.tsx:11-68` (approve/reject/execute UI), `action_queue.py:11-26` (T0/T1/T2 tiers) | Wave 2 Chat Concierge | — |
| 6 | Chat references canonical objects that the user can open elsewhere | **EXISTS** | `context-references.ts:1-7` (ContextReference kind/id/label), `InputBar.tsx:236-257` (context ref chips with remove button and kind label) | Wave 2 Chat Concierge | — |

## 5. Linear Inbox — attention should terminate in action

| # | Steal specifically | Status | Evidence | Wave destination | Gap note |
|---|-------------------|--------|----------|-----------------|----------|
| 1 | `Needs you` is a first-class queue, not one card among many | **EXISTS** | `HomeState.tsx:1507` (dedicated NeedsYou component), `HomeState.tsx:1541,1551,1614` (SectionCard title="needs you"), `WorkView.tsx:16-19` (needs-you group) | Wave 3 Home Action Board | — |
| 2 | each item owns a next action | **PARTIAL** | `WorkView.tsx:279-305` (rowAction computes next_action for work items), `WorkView.tsx:185-186` (state/next_action grouping) | Wave 3 Home Action Board | Work items and action-queue items have a next action; but deadlines, insight items, triage entries, and signals in Home have no next_action — they are static info cards |
| 3 | resolving the underlying object updates/removes the attention item automatically | **PARTIAL** | `HomeState.tsx:1518-1523` (Actions filtered by attention statuses, deduped by Map), `HomeState.tsx:1563` (approveAndExecuteAction updates outcome) | Wave 3 Home Action Board | Abandoning items works via query refetch (action status changes), but no event-driven removal or cross-object cascade when the underlying task/project is resolved from another surface |
| 4 | allow deferral only where there is an authoritative schedule/reminder model | **PARTIAL** | `InsightReturnCard.tsx:49-50,93,97` (snooze on insight items), `deadline_store.py` (deadline schedule model) | Wave 3 Home Action Board | Deferral exists only for insight-loop items; Needs You actions have no snooze/defer; deadlines have a schedule model but no UI for deferring attention items |
| 5 | fast next/previous traversal can come later if the queue becomes dense | **MISSING** | No keyboard-based next/previous navigation in HomeState or NeedsYou | Wave 3 Home Action Board | No arrow-key, j/k, or tab-order traversal for the attention queue; user must scroll or click to reach each item |
| 6 | passive context belongs below the fold or behind disclosure | **PARTIAL** | `HomeIntelligence.tsx:31` (items limited to 3), `HomeState.tsx:1965-2031` (layout: intelligence first, then NeedsYou, then tiles) | Wave 3 Home Action Board | Intelligence items are capped but there are no disclosure/accordion patterns for less urgent info; everything is flat sections |

## 6. Linear's product lesson — sophistication hides in repeated small costs

| # | Steal specifically | Status | Evidence | Wave destination | Gap note |
|---|-------------------|--------|----------|-----------------|----------|
| 1 | baseline alignment | **PARTIAL** | `globals.css:130-142` (spacing tokens), many inline style objects in `HomeState.tsx` | Wave 5 Precision | Token system exists but is inconsistently consumed — many components define pixel values inline |
| 2 | row height consistency | **MISSING** | No unified row component (row heights vary per component, e.g. `WorkView.tsx:251` vs `HomeState.tsx` inline styles) | Wave 5 Precision | No standard row/ListItem component; every section defines its own height/padding |
| 3 | text hierarchy | **PARTIAL** | `globals.css:118-120` (`--font-display`, `--font-body`, `--font-mono`), no heading scale tokens (h1-h6) | Wave 5 Precision | Font family tokens exist but no typographic scale; headings use element-level styling |
| 4 | icon optical alignment | **MISSING** | No icon alignment audit visible; icons from lucide-react used directly without alignment wrapper | Wave 5 Precision | No standard Icon component with optical alignment correction |
| 5 | predictable primary action placement | **PARTIAL** | `ActionCard.tsx:68,73` (consistent approve/run buttons), `WorkView.tsx:466,492` (primaryActionStyle per row) | Wave 5 Precision | Primary action placement is consistent within ActionCard but not universal across Home, Work, and other surfaces |
| 6 | stable loading geometry | **MISSING** | `HomeState.tsx:1542-1544` (loading text), `Skeleton.tsx` exists but not used for component-level loading states | Wave 5 Precision | Most loading states are text strings, not skeleton/shimmer placeholders; layout jumps on data arrival |
| 7 | focus restore | **PARTIAL** | `Dialog.tsx` (focus trap on open), no universal focus-restore pattern | Wave 5 Precision | Dialog has focus management but most state transitions (loading → data, action approval → outcome) do not restore focus to the last active element |
| 8 | menus/sheets anchored where invoked | **MISSING** | No contextual menus or anchored sheets exist | Wave 5 Precision | Menus and sheets exist (Dialog.tsx Sheet component) but none are anchored to the invoking element; they're always centered overlays |
| 9 | keyboard continuity | **MISSING** | Limited to CommandPalette and textarea `@` picker keyboard nav | Wave 5 Precision | No keyboard-first navigation for surfaces; Home, Work, Projects rely on tab-to-element with no spatial navigation |
| 10 | deliberate truncation/wrapping | **MISSING** | No systematic truncation or wrapping logic visible | Wave 5 Precision | Long titles, action descriptions, and error messages are not consistently truncated or wrapped; no line-clamp pattern |
| 11 | touch target consistency | **PARTIAL** | `WorkView.tsx:246` (`minHeight: 44` on primaryActionStyle), `InputBar.tsx:227` (`controlSize: 44` or 40) | Wave 5 Precision | Some interactive targets use 44px min-height, but many small buttons (e.g. HomeState approve buttons) lack minimum touch target size |
| 12 | zero accidental horizontal scroll | **NOT AUDITED** | Requires runtime verification | Wave 5 Precision | Cannot verify without running the app; no viewport-width constraints visible in CSS |
| 13 | no layout jump when state changes | **MISSING** | `Skeleton.tsx` exists but unused; loading → data transitions use text placeholders that shift layout | Wave 5 Precision | No stable-geometry containers that reserve space before data arrives; most components shift when content loads |