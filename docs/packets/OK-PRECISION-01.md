# OK-PRECISION-01 — Visual Precision Contract

## Mission

Turn Kitty's existing design-system principles into enforceable visual geometry so surfaces stop being merely token-compliant and start looking intentionally authored.

This packet defines and implements the shared precision primitives. It is not the broad surface cleanup yet.

## Product acceptance moment

Place Home, Chat, Projects, Library, Work, and Image Lab side by side. Their text baselines, row heights, buttons, icons, content widths, headings, and state treatments clearly belong to one system before any mascot/illustration is added.

## Why this packet exists

Earlier coherence work proved semantic-token adoption but still left bespoke inline styling and domain-local component variants. Token compliance does not guarantee:
- aligned baselines;
- consistent control geometry;
- coherent typographic hierarchy;
- predictable row/card anatomy;
- stable loading geometry;
- consistent action placement.

## Define the precision contract

Use existing semantic tokens and evolve them only where necessary.

### Typography roles
Define reusable roles, not arbitrary component font sizes:
- page title;
- section title;
- object title;
- body;
- secondary body;
- metadata;
- control label;
- technical evidence/mono.

For each role establish:
- font family;
- font size;
- line height;
- weight range;
- letter spacing where needed;
- allowed contexts.

Avoid 9–11px persistent product labels except genuinely dense metadata where accessibility remains acceptable.

### Control geometry
Lock:
- small/regular/large control heights;
- phone persistent target >= 44px;
- horizontal padding;
- icon sizes;
- icon/text gap;
- radius;
- focus ring geometry;
- disabled treatment.

Primary action prominence is semantic, not just a saturated color.

### Surface geometry
Lock:
- page max widths / gutters;
- rail/panel gaps;
- section spacing;
- row padding;
- list separator rules;
- card padding only for true cards;
- dense evidence panel spacing;
- mobile sheet/dialog insets.

### Alignment
Define:
- title + trailing action baseline;
- icon optical alignment;
- status + title rows;
- numeric/count alignment;
- avatar/mascot alignment when present;
- composer/control vertical centering.

### State geometry
Loading, empty, error, waiting, blocked, and completed states should preserve the approximate structure of the content they replace. Avoid layout jumps.

## Implementation location

Prefer existing runtime token/component sources rather than a second stylesheet universe:
- `gateway/kitty-chat/src/app/globals.css`
- existing shared UI primitives / `lib/ui`
- shared Button/Dialog/Sheet/etc.
- new typography/layout primitives only where they replace repeated bespoke geometry.

Do not rewrite every domain component in this packet.

## Reference lessons

### Linear
Steal the principle that repeated tiny interaction costs matter. Precision includes menu anchoring, focus behavior, predictable geometry, and pointer/keyboard continuity — not only CSS aesthetics.

### Anthropic
Steal coherence through a consistent design system and selective expressive moments. Do not copy Claude's palette, illustrations, or exact compositions.

## Tests / evidence

Automated where practical:
- shared primitive snapshots/DOM structure;
- focus-visible behavior;
- touch target dimensions if test harness supports layout;
- no unapproved raw type/control geometry in migrated primitives.

Running-product evidence required:
- ~390px phone;
- ~430px phone;
- laptop;
- large desktop;
- light and dark canonical themes where supported;
- keyboard navigation;
- reduced motion;
- no document-level horizontal scroll.

## Non-goals

- Full per-surface visual cleanup.
- New theme family.
- Mascot/illustration work.
- Changing information architecture.
- Replacing domain-specific layouts that have a valid reason to differ.

## Done when

A subsequent surface packet can migrate to named typography/control/layout primitives rather than inventing dimensions locally, and running product comparison shows clear cross-surface visual convergence.
