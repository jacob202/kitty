# OK-BRAND-01 — Kitty Character + Illustration Language

## Mission

Create a restrained, reusable Kitty illustration/mascot language that gives the product recognizable personality without turning working surfaces into decoration.

## Hard dependency

Do this after `OK-PRECISION-01` and enough surface precision work that typography, spacing, control geometry, and hierarchy already stand on their own.

Brand is punctuation, not camouflage.

## Product acceptance moment

A user sees a Home greeting, an empty Library state, a meaningful waiting state, and an offline state. The illustrations clearly come from one Kitty family, reinforce the state, and never replace the state text/action.

## Existing Kitty seed

The repo already contains a `KidCatDoodle` concept / cat assets and design guidance that mascot use should be sparse and functional. Preserve the useful identity seed; do not scatter one-off SVGs across components.

## Reference principle

Study Anthropic/Claude's public editorial illustration strategy:
- simple recognizable visual motifs;
- expressive moments around otherwise calm product/brand surfaces;
- coherence across a family rather than one giant mascot treatment.

Do not reproduce Claude's character, logo, color palette, exact drawing style, layouts, or brand copy.

## Canonical state family

Start with a small closed set. Suggested:

1. `hello`
2. `thinking`
3. `working`
4. `waiting`
5. `found`
6. `success`
7. `empty`
8. `offline_sleeping`
9. `creative`
10. `builder`

Do not add new poses ad hoc in feature components. New states require a clear product need.

## Illustration rules

Define:
- silhouette/proportions;
- stroke language;
- fill policy;
- acceptable semantic accent colors;
- expression vocabulary;
- minimum/maximum display sizes;
- monochrome behavior;
- dark-mode behavior;
- reduced-motion behavior;
- when animation is prohibited/allowed;
- accessible accompanying copy requirements.

## Usage rules

Good candidates:
- Home greeting / rare delight moment;
- onboarding;
- true empty states;
- meaningful wait states;
- success after a consequential workflow;
- offline/degraded state;
- Image Lab creative context;
- Builder working context where it does not hide evidence.

Bad candidates:
- every section heading;
- every card;
- buttons;
- routine navigation;
- status indication without text;
- technical evidence/log surfaces;
- repeated decoration that competes with content.

## Implementation

Prefer one canonical asset/component system, for example:
- `components/brand/KittyIllustration.tsx`
- `public/kitty/` or existing appropriate asset directory
- variant/state prop rather than bespoke component copies.

If generated/vector assets are used, store source/provenance and keep runtime assets optimized.

## First migration

Use only 3–4 surfaces/states as proof:
- Home greeting;
- one empty state;
- one success/wait state;
- offline/degraded.

Do not blanket-migrate the app in this packet.

## Acceptance

- illustrations are recognizably one family;
- states remain understandable with illustrations hidden;
- no new horizontal overflow or layout jump;
- dark/light usage remains legible;
- illustration does not become the primary interaction target;
- normal working screens remain visually calm.

## Non-goals

- Full marketing rebrand.
- New logo requirement.
- Claude imitation.
- Animated mascot assistant roaming the UI.
- Rewriting Kitty's conversational personality.
