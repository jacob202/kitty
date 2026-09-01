# OK-PASS-01 — Ruthless Product Acceptance Pass

## Mission

Perform the final running-product pass that removes residual inconsistency, dead weight, fake affordances, accidental layout, and generic/generated-looking UI after the ONE KITTY primitives are integrated.

This is not a new audit backlog. Every finding must terminate in FIX, DELETE, explicitly PARK, or REJECT.

## Scope

Primary surfaces:
- Home
- Chat
- Work
- Projects
- Image Lab
- Library
- Automations
- Settings

Secondary/common surfaces:
- navigation/rail/bottom nav
- dialogs/sheets/menus
- Activity Center
- Artifact Canvas
- command/capability launcher
- context picker

## Viewports / modes

At minimum:
- ~390px phone
- ~430px phone
- laptop
- large desktop
- light canonical theme
- dark canonical theme
- reduced motion
- keyboard-only path for primary flows

## Review questions

For every visible element:

1. Why is this here?
2. Is it the right hierarchy?
3. Does it align with neighboring structure?
4. Is its text size/line-height consistent with its role?
5. Is the copy product-facing and concise?
6. Does it look interactive only if it is interactive?
7. If clicked, does something real happen?
8. Is action feedback immediate and truthful?
9. Is information duplicated elsewhere on the same screen?
10. Could this be removed?

For every screen:

- Is the first action obvious?
- Is there unnecessary card nesting?
- Is the page width intentional?
- Are headings/rows aligned?
- Do loading/error/empty states preserve the structure?
- Does mobile feel composed rather than squeezed?
- Is there any document-level horizontal scroll?
- Does Back work predictably?
- Does reload/restart preserve anything that claims persistence?
- Are technical internals hidden until requested?
- Are mascot/brand moments helping rather than cluttering?

## Actionability rule

No prominent card may survive this pass unless it has at least one of:
- a real action;
- a critical status/decision the user must know;
- uniquely valuable read-only intelligence that cannot reasonably be demoted.

Generic summaries and counts are deletion/demotion candidates.

## Precision rule

Fix “almost the same” variants:
- button heights/padding;
- 11px versus 12px versus 13px arbitrary labels;
- mismatched icon sizes;
- inconsistent title baselines;
- random radii;
- card padding drift;
- different hover/focus behavior;
- inconsistent empty-state alignment;
- accidental monospace usage.

Do not flatten valid domain differences.

## Evidence

For each surface record:
- viewport(s) checked;
- flows exercised;
- before/after screenshot or short capture for material visual changes;
- degraded/failure path where applicable;
- reload/restart path where persistence is claimed;
- FIX/DELETE/PARK/REJECT ledger.

## Exit gate

The campaign does not exit on “tests green.” It exits when running-product acceptance confirms:

- cohesive visual grammar;
- clear primary hierarchy;
- all prominent actions work;
- cross-surface objects preserve identity/truth;
- no accidental horizontal scroll;
- phone layout is intentional;
- no stale/dead UI remains in the primary paths;
- brand character is restrained;
- no known P0/P1 product-trust regression remains.
