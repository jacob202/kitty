# Kitty — Design Brief

This is the design constitution for the Kitty product surface. It exists so
future `/design` work doesn't re-ask basics or drift toward generic defaults.

## Register

**Product.** Kitty is a local-first personal AI companion app. The interface is
an instrument, not a marketing page: it earns trust through consistency, speed,
and honest state, not through art-directed hero moments. One exception — the
mascot and empty states are allowed real warmth; they are the product's voice,
not decoration.

## Name, category, user

- **Name:** Kitty (wordmark is lowercase `kitty` in the UI; brand mark is a
  hand-drawn crayon cat).
- **Category:** personal AI companion. The first thing a person should be able
  to do is *talk to it*.
- **Primary user:** Jacob, on a Mac desktop and an iPhone-class phone. He is
  arriving to give Kitty meaningful work, watch progress, ask questions, and
  recover from failure. He is not an operator of a status dashboard.

## Product purpose (the single most important job)

Talk to Kitty and get a real result. The conversation is the core artifact.
Everything else — Home, Work, Library, Automations, Image Lab — exists to
support or recover that conversation, not to compete with it for the first
viewport.

The mission's governing rule is non-negotiable and drives layout and copy:

> Every surface must be actionable in place. Information the user cannot act on
> right there is a defect, not a feature.

## Voice

- **Warm, hand-drawn, character-first.** The crayon cat ("drawn by a
  six-year-old, allegedly") is the product's personality kernel. Copy can be a
  little playful ("hey.", "let's go →") but never cutesy over substance.
- **Plain language everywhere.** No raw HTTP status, no "gateway", no provider
  names, no stack traces, no internal service names. Errors are recovery paths:
  what broke, and what to do next.
- **Sentence case, one verb per action.** No exclamation points.

## Anti-references (what Kitty is not)

- **Not a generic violet SaaS.** The current `--color-accent: #6557D9` is the
  AI-startup default and must be replaced with a hue from the cat's own world
  (warm ginger / ink). No blue-violet CTAs, no indigo-to-cyan gradients.
- **Not a dark terminal developer tool.** Kitty is warm and human, not a
  monospace console. Mono is for data, never the primary voice.
- **Not a centered hero with feature-tile grid.** The product's dominant work
  pattern is *converse + recover*, not a landing page.
- **No neubrutalist / chunky-block / sticker defaults.** The warmth is crayon
  and ink, not hard black borders and offset shadows.

## Visual foundation (what exists in the repo today)

- **Themes:** `cosmic` (default), `day`, `night`, driven by semantic CSS custom
  properties in `gateway/kitty-chat/src/app/globals.css`. Any visual change must
  respect all three themes, not just cosmic.
- **Type tokens:** `--font-display: "Avenir Next"`, `--font-body: Inter`,
  `--font-mono`. Split personality — future work should resolve this into one
  voice (likely the warm humanist display voice, with mono reserved for data).
- **Mascot:** `gateway/kitty-chat/src/components/CrayonCat.tsx` — four honest
  states (idle, working, done, broke) rendered as hand-drawn SVG with ink
  outlines. This is the strongest authored asset and should own more of the
  surface, not less.
- **Shared card/type tokens:** `gateway/kitty-chat/src/lib/ui.ts` (card,
  cardHeader, itemCard, bodyText, etc.).
- **Layout shell:** rail (desktop) / bottom nav (mobile), topbar, status bar,
  and a view renderer switching between Home, Chat, Work, Library, Studio,
  Projects, Automations, Settings.

## Design principles

1. **Conversation first.** Chat is the arrival surface or the primary composer
   is present on arrival. A user must never have to hunt for the text box.
2. **One authored identity.** The crayon/ink warmth of the mascot extends into
   color, type, edges, and motion across the whole shell. No more "mascot in
   one corner, generic SaaS everywhere else."
3. **State is first-class.** Every surface renders honest idle, loading, empty,
   error, disabled, and overflow states. A layout that only works in the happy
   path is a sketch.
4. **Plain language beats clever.** Copy names the real work and the real
   recovery. No jargon.
5. **Actionable in place.** If something is on screen, the user can act on it
   there, or the screen says plainly why not.

## Accessibility expectations

- Native elements first: real `<button>` for actions, `<a href>` for
  navigation, never `<div onClick>`.
- Visible `:focus-visible` rings (never bare `outline: none` without
  replacement).
- 44px minimum touch targets.
- No meaning carried by color alone; state is always paired with text, icon, or
  shape.
- Keyboard path must complete every flow without a mouse.
- `prefers-reduced-motion` respected (already wired via `useReducedMotion`).

## Component rules

- **Buttons:** one verb, sentence case. Primary uses the (future) accent; the
  accent stays rare enough to mean something (the "protagonist", ~10% of the
  surface).
- **Cards:** allowed only for genuinely discrete, self-contained, scannable
  content. Not a default wrapper. Hover-only affordances are banned; any
  clickable card item shows a visible rest-state cue (edge or chevron).
- **Mono:** for data, counts, metadata, and technical detail only. Not for
  headings or body prose.

## Composition lanes (allowed, by surface)

- **Chat:** operate — a focused conversation with the composer and recovery
  close at hand.
- **Home:** decide — one dominant "what matters now" with a single primary
  action, not a wall of equal cards.
- **Work / Builder:** monitor — status, change, priority, with retry/recovery
  in place.
- **Library / Studio:** explore — search, browse, detail, and return.
- **Settings:** configure — grouped decisions with clear commit areas.

## Working notes (assumptions to revisit)

- Register is **product**, not brand — unless the mascot's warmth pulls the
  product toward a more expressive identity over time.
- The primary user is Jacob today; any multi-user future must re-derive the
  "primary user under pressure" line before proceeding.
