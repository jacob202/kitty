# Kitty Collaborative Leverage Swarm -- Final Results

**Date:** 2026-09-02
**Baseline SHA:** 56b6163b (local main, 11 commits behind origin/main 7594372d)
**Panel:** 7/9 specialists completed (Performance and Adversarial QA failed mid-run)
**Findings:** 59 total, 12 independently verified, 2 rejected, 4 demoted by skeptic
**Runtime:** gateway :8000, UI :4000, LiteLLM :8001 (running), Ollama (NOT running)

---

## 1. EXECUTIVE BRIEF

Kitty has capable backend intelligence that the frontend fails to consume. Three composite endpoints (/state/now, /brief, /intelligence) already exist but the home dashboard makes ~24 individual HTTP requests instead -- including a 55KB payload every 120 seconds just to count chats. The design system defines hover and focus-ring tokens that no component uses. The AI gateway streams which model was actually used, but the client drops that header. Five backend capabilities (/magic, /life/proactive, /chronicle/tips, /nudges, /telos) return real data with zero frontend callers.

The F-017 root cause is at the consumption layer, not the data layer: the backend composes intelligence; the frontend fetches each source individually.

---

## 2. TOP 3 MOVES (skeptic-reviewed, evidence-verified)

### Move 1: Consolidate Home Dashboard Fetches
**Effort:** M | **Impact:** F-017 root cause, performance, reliability

Verified problems:
- useActions('proposed') called in BOTH WhatsNext (HomeState.tsx:753) AND NeedsYou (HomeState.tsx:1508)
- NeedsYou makes 5 separate /actions calls (proposed, approved, failed, unknown, outcome_unknown)
- fetchChatsPersistence downloads /chats (55KB) every 120s just to count -- /state/now already has chats.count (verified: 13)
- Mutation hooks in 3 component trees cause 3x cascade refetches on each approve/reject
- /brief endpoint exists with next_steps but HomeState doesn't use it

Fix: Consume /state/now for chats.count + signals.count. Add /actions?status=needs_attention. Lift mutations to shared context.

Skeptic verdict: UPHOLD -- 'Best finding in the set -- specific, actionable, non-trivial'

### Move 2: WCAG AA Contrast + Mobile Tap Targets + Hover States
**Effort:** S | **Impact:** every surface, ACCEPT-001 compliance

Verified problems:
1. Contrast: --color-text-muted is 3.45:1 (cosmic), 3.44:1 (day). WCAG AA requires 4.5:1. Night passes at 5.90:1.
2. Tap targets: actionButtonStyle has 21px hit area. Need 44px. 19+ instances.
3. Hover: --color-interactive-hover defined in all 3 themes but zero :hover rules use it.
4. Color-only: HealthDot uses colored circle with no text/icon for color-blind users.

Verified fixes:
1. Cosmic: --color-text-muted: #677191 (4.55:1). Day: #787165 (4.55:1). Night: unchanged.
2. Add minHeight: 44 to actionButtonStyle and primaryButtonStyle
3. Add CSS rule: button:hover:not(:disabled) { background: var(--color-interactive-hover); }
4. Add aria-label to HealthDot with tone prefix

### Move 3: AI Transparency -- Routed Model + Memory Evidence
**Effort:** S | **Impact:** trust, one intelligent agent feel

Verified problems:
1. completions.py:892 emits X-Kitty-Model-Selected. chat-client.ts:149-151 doesn't capture it. Actual model invisible.
2. KittyContext.tsx:652 suppresses memoryItems on smalltalk. Server sends evidence, client drops it.

Fixes: Capture one header. Remove isSmalltalk guard.

---

## 3. TOP 10 EVIDENCE-BACKED OPPORTUNITIES (final ranking)

| # | Finding | Evidence | Effort | Skeptic |
|---|---------|----------|--------|---------|
| 1 | Consolidate home fetches | 51 hooks, 55KB/120s, 3x refetch | M | UPHOLD |
| 2 | WCAG contrast fix | 3.45:1 verified, fix 4.55:1 verified | S | UPHOLD |
| 3 | Routed model header | completions.py:892 emits, client drops | S | UPHOLD |
| 4 | Signal TTL + batch dismiss | 211 unprocessed, no cleanup | S | DEMOTE |
| 5 | Mobile tap targets | 21px verified, 19+ instances | S | UPHOLD |
| 6 | Hover states | token defined, 0 :hover rules | S | UPHOLD |
| 7 | Memory smalltalk suppression | KittyContext.tsx:652 guard | S | UPHOLD |
| 8 | Image Lab use-in-chat | useArtifactInChat exists, ImageLab doesn't call | M | CONDITIONAL |
| 9 | Tutor/Journal discoverability | Only in CommandPalette | S | DEMOTE |
| 10 | /chronicle/tips | Returns real tips, zero callers, NOT in /intelligence | S | DEMOTE |

---

## 4. ROOT-CAUSE CLUSTERS

### Cluster 1: Frontend ignores backend composition (F-017)
Findings: A-002, D-004, E-001, E-002, E-003, E-004, E-007
Root cause: Backend has composites. Frontend fetches individually.
One fix: Consume /state/now + add /actions?status=needs_attention + lift mutations

### Cluster 2: Design system primitives exist but aren't adopted
Findings: B-001, B-002, B-005, B-006
Root cause: ui/Button and CSS tokens built but never enforced
One fix: CSS hover rule + adopt Button + standardize disabled opacity

### Cluster 3: Mobile/a11y gaps in shared primitives
Findings: C-001, C-003, C-004, C-009
Root cause: Primitives designed without WCAG verification
One fix: CSS value changes + minHeight + aria-label

### Cluster 4: AI transparency gaps
Findings: F-003, F-004, F-008
Root cause: Transparency treated as debugging, not user evidence
One fix: Capture X-Kitty-Model-Selected + remove isSmalltalk guard

### Cluster 5: Hidden capabilities with no UI exposure
Findings: I-001 through I-008, A-008
Root cause: Built as backend modules, never promoted to nav
Note: /magic and /life partially addressed upstream by /intelligence (PR #778)

### Cluster 6: Signal noise accumulation
Findings: A-001, D-001, D-002
Root cause: Append-only store, mark_processed one at a time, no TTL
One fix: TTL for processed >30 days + batch dismiss by source

---

## 5. HIDDEN CAPABILITY UNLOCKS

| Capability | Endpoint | UI Exposure | Upstream |
|-----------|----------|-------------|----------|
| Cross-project connections | /magic | ZERO local | /intelligence (PR #778) |
| Life awareness | /life/proactive | ZERO local | /intelligence (PR #778) |
| Multi-agent council | /council | ZERO | Not addressed |
| Personalized tips | /chronicle/tips | ZERO | NOT in /intelligence |
| Dropped thread nudges | /nudges | ZERO | Not addressed |
| Purpose tracking | /telos | ZERO | Not addressed |
| Pattern analysis | /patterns/weekly | ZERO | Not addressed |
| Deep research | /research/deep | DEAD VIEW | ResearchView.tsx added upstream |
| Dream insights | /dream/insights | Count only | Not addressed |

---

## 6. REJECTED FINDINGS

| Finding | Reason |
|---------|--------|
| A-004 (Projects missing from Rail) | Projects IS in Rail.tsx:8 |
| B-004 (no focus rings) | globals.css:167 has :focus-visible |
| F-001 (memory collapsed by default) | Design preference, not defect |
| I-001 (/magic no callers) | Partially addressed by /intelligence upstream |

---

## 7. PROPOSED EXECUTION ORDER

1. CSS contrast + tap targets + hover (S, 15 min) -- zero risk, immediate quality
2. Routed model header capture (S, 30 min) -- one header line
3. /chats -> /state/now consolidation (S, 30 min) -- 55KB to 0KB
4. Signal TTL (S, 1 hr) -- age-based cleanup in signal_store.py
5. Memory smalltalk guard removal (S, 5 min) -- remove !isSmalltalk
6. useActions consolidation (M, 2 hr) -- /actions?status=needs_attention
7. Mutation hook dedup (M, 2 hr) -- lift to shared context
8. Image Lab use-in-chat (M, 3 hr) -- wire existing useArtifactInChat
9. Tutor/Journal to More menu (S, 15 min)
10. /chronicle/tips banner (S, 1 hr)

---

## 8. EVIDENCE GAPS

1. Performance specialist failed -- no measured LCP/INP or bundle size data
2. Adversarial QA failed -- race conditions inferred from code, not tested
3. Offline-first behavior not evaluated
4. Council endpoint not tested end-to-end
5. Whether /intelligence should replace individual fetches or remain extra card

---

## SUCCESS CRITERION

How much additional Kitty capability, quality and development leverage can be obtained from the fewest well-chosen changes?

Answer: Three CSS value changes fix WCAG AA across every surface. One header capture makes AI routing transparent. Pointing one fetch at an existing endpoint eliminates 55KB per 120 seconds. None covered by existing PRs.