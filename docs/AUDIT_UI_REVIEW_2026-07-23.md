# UI Review Synthesis — July 2026

6 perspectives: UX, Visual, Performance, Mobile, Accessibility, First-Use.

## P0 — Ship Immediately (blocks daily use)

| # | Issue | Source | Fix |
|---|-------|--------|-----|
| 1 | Home empty state is a ghost town | First-Use, UX | Add greeting + one prompt suggestion + rail icon labels |
| 2 | UI doesn't start — needs manual `cd && npm run dev` | Perf, First-Use | `./kitty up` should include frontend |
| 3 | Self-repairs endpoint exists but isn't surfaced | First-Use, UX | Home card linking to /repairs results |

## P1 — This Week

| # | Issue | Source | Fix |
|---|-------|--------|-----|
| 4 | Bottom tab bar missing on mobile (desktop-only rail) | Mobile | Add BottomNav.tsx mirroring 7-surface rail |
| 5 | No code splitting — all surfaces bundle on first load | Perf | Use next/dynamic in view registry |
| 6 | Touch targets under 40px | Mobile | Audit all interactive elements, enforce 40px min |
| 7 | Cat SVG filters kill GPU on low-power devices | Perf, Visual | Replace feTurbulence with CSS transitions |
| 8 | Status colors only — no text/pattern fallback | A11y | Add text labels alongside color-only indicators |

## P2 — Next Two Weeks

| # | Issue | Source | Fix |
|---|-------|--------|-----|
| 9 | Typography: too much monospace, no scale | Visual | Define 4-level scale, use sans-serif for UI chrome |
| 10 | No ARIA landmarks or heading hierarchy | A11y | Add h1 per surface, main/aside landmarks |
| 11 | Missing form labels on inputs | A11y | aria-label on chat input, search, todos |
| 12 | Double-fetching data on inactive surfaces | Perf | enabled:false until surface is active |
| 13 | No keyboard shortcuts for surface switching | A11y | Cmd+1-7 for each surface |
| 14 | No focus management on view transitions | A11y | Focus panel heading on surface change |

## P3 — Polish

| # | Issue | Source | Fix |
|---|-------|--------|-----|
| 15 | Runtime manifest polls even on hidden tabs | Perf | Pause on visibilitychange |
| 16 | Pull-to-refresh missing on mobile | Mobile | Add to Home + Library + Work |
| 17 | Too many colors in palette (~20 CSS vars) | Visual | Reduce to 5-color semantic palette |
| 18 | No spacing system — 13 different padding values | Visual | Adopt 4px base unit |
| 19 | No progressive disclosure for new users | First-Use | Hide advanced surfaces until first use |
| 20 | Chat disconnects from other surfaces | UX | Add "jump back to chat" thin notification bar |
| 21 | Terminal hidden in Settings — should be global | UX | Cmd+J slide-up from any surface |
| 22 | React.memo missing on large lists | Perf | Add to TaskPanel WorkCard list |

## Summary

22 issues across 6 perspectives. P0 (3 items) blocks daily use. P1 (5 items) fixes the mobile and a11y gap. P2 (6 items) professionalizes the experience. P3 (8 items) is polish.
