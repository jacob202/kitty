# OK-PRECISION-SHELL — Shell + Navigation Precision Migration

## Mission

Apply the shared precision contract to Kitty's global shell and navigation before surface-specific polish, so every page inherits consistent geometry and interaction behavior.

## Depends on

`OK-PRECISION-01`.

## Scope

Likely components:
- `Rail.tsx`
- `TopBar.tsx`
- `BottomNav.tsx`
- shared page container/layout
- common Dialog/Sheet/menu primitives
- SessionSidebar where it is part of shell behavior

Verify exact current names after WOW integration.

## Acceptance

- page content begins on a consistent grid/gutter;
- active navigation treatment is consistent and accessible;
- icons share optical size/alignment;
- nav controls meet touch target rules;
- secondary destinations do not squeeze mobile primary navigation;
- sheets/dialogs use consistent insets/radii/headers;
- focus trap/restore works;
- no shell-induced horizontal scroll;
- top/bottom fixed regions correctly reserve safe-area/content space.

## Non-goals

- content redesign inside Home/Chat/etc.;
- brand illustration rollout;
- new navigation destinations.
