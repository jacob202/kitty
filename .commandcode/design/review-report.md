# Kitty — Design Review

**Mode:** `/design review`
**Surface:** `gateway/kitty-chat` (native Next.js chat product)
**Date:** 2026-08-30
**Scope:** whole product experience, basics-first (workflows), finishing details second (mascot, color, type)

---

## First impression

Kitty opens on **Home**, not Chat. Home is a dense dashboard of cards —
"what's next", "needs you", "today", "deadlines", "active projects", then a
collapsed "More context" and "System & setup" disclosure. The first thing a
new user sees is a wall of monitoring panels, not the thing the product is
named for.

The personality lives almost entirely in one place: a hand-drawn crayon cat
(`CrayonCat.tsx`) and a "hey." empty state (`KittyThread.tsx`). The rest of
the product is a standard SaaS dashboard — white cards, hairline borders,
`--color-separator` grays, a purple-violet accent. The mascot and the product
shell feel like two different products glued together.

The name is Kitty. The category is a personal AI companion. The job is: talk
to it, give it work, get results, recover from failure. The most important
artifact is the **conversation**, and the most important action is **sending a
message**. Right now neither is the first thing a user meets.

---

## The experience walk

### Arrival

A user lands on Home. They see a "good morning" headline, a health strip, and
a 2-column grid of cards. None of it is a text box. The chat input is hidden
behind a rail icon and an empty state that only exists once they click into
Chat. To actually *use* Kitty they must know to switch views. The primary job
of the product is one click away from the surface it opens on.

### Sending a message

Once in Chat, the composer is competent: `InputBar.tsx` has an accessible
textarea (`aria-label="Message Kitty"`), a paperclip, mic, and model override.
Attachments render as chips. But the empty state is a single "hey." plus a
44px "let's go →" button and four suggestion chips — fine, but it inherits the
generic SaaS empty-state shape rather than feeling like the product's voice.

### Waiting / streaming

Streaming shows a "thinking…" label and a typing-dots bubble. The corner cat
breathes. This is the strongest authored moment in the product — it has
character. It is also the *only* strong authored moment.

### Failure / recovery

`StatusBar.tsx` is genuinely well-built: one ranked line, plain-language
recovery, retry controls, honest "save failed" vs "offline" distinction. The
copy discipline here (no raw HTTP, no "gateway", no jargon) is the best in the
app. The problem is the *visual* failure state is a thin mono line, while the
success/identity state is a big friendly cat. The most important trust signal
(what went wrong) is the least visually present.

---

## What's working

- **Honest copy discipline.** `StatusBar`, `HealthSurfaceCard`, and the
  failure-copy layer translate every backend error to plain language. No raw
  status codes, provider names, or "gateway" leaks into user-facing text.
  This is the product's single strongest asset.
- **Accessible controls.** Buttons are real `<button>`s with labels, focus
  rings come from the platform (`:focus-visible`), hit targets are 44px+.
  The keyboard path is genuinely there.
- **One mascot with real states.** `CrayonCat` has idle/working/done/broke
  with distinct eyes and mouths — this is the kernel of a real identity.

---

## Findings

| # | Severity | Discipline | Location | Before | After | Why |
|---|---|---|---|---|---|---|
| 1 | HIGH | Composition | `src/app/page.tsx` (default view `home`), `KittyContext.tsx:268` | App boots into a monitoring dashboard; the chat composer is not on the first surface | Make Chat the arrival surface, or put a primary composer on Home so "talk to Kitty" is the first thing | The product's core job (conversation) is one click away from the surface it opens on; a new user meets a wall of status cards, not the thing Kitty is for |
| 2 | HIGH | Voice | `CrayonCat.tsx` (hand-drawn SVG) vs `globals.css` + `ui.ts` (generic SaaS: white cards, hairline borders, `--color-separator`, violet accent) | The mascot and the shell are two different visual products | One authored visual language across both — the crayon/ink cat's warmth extended into type, color, and edge treatment, or the mascot retired in favor of the current shell | The only place the product has a point of view is the mascot; everywhere else it is a median SaaS dashboard. The two fight each other |
| 3 | MEDIUM | Type | `globals.css:115-116` (`--font-display: "Avenir Next"`, `--font-body: Inter`); `ui.ts:44` (mono meta everywhere) | Identity is split across a display sans, a body sans, and a heavy monospace for all meta/counts; no typographic voice | Pick one system: either the warm humanist display voice of the cat, or the utilitarian mono console — not both fighting | The type does not match the mascot's character, and the monospace-for-everything habit reads as "developer tool" by default |
| 4 | MEDIUM | Color | `globals.css:19` (`--color-accent: #6557D9`), `ui.ts` (purple/violet accent) | Blue-violet accent as the product's only identity color | A hue tied to the cat's world (warm ginger/ink, per the mascot's `--cat-ginger`) as the semantic accent; keep violet only if it earns a role | The accent is the generic tech hue — the same purple the smell catalog flags as the AI-startup shorthand. It says nothing about Kitty |
| 5 | MEDIUM | Interaction | `HomeState.tsx` (cards map to `itemCard` with `onMouseEnter` border swap); `ui.ts:67` | Hover-only affordance on card items (`transition: border-color`, `onMouseEnter`/`onMouseLeave`) | A visible rest state for interactive items (border/edge or a chevron), not a hover-revealed cue | The affordance that an item is clickable only appears on hover; touch users never see it, and it's exactly the "hover: hover" gating the discipline forbids |
| 6 | LOW | Layout | `KittyThread.tsx` (`viewportStyle` paddingBottom 176/140) and `page.tsx` composer | Composer floats over the thread with a hard fixed padding reserve | Reserve exactly one composer height via the layout, not a magic `176`/`140` offset | Fragile spacing that must be re-tuned when the composer changes; a layout-level reserve is the correct fix |
| 7 | LOW | Writing | `KittyThread.tsx` empty state ("hey." / "let's go →") | The product's one chance to establish voice uses a generic empty-state greeting | A Kitty-specific opening that names what it can do and what to ask first | It's the only authored copy in Chat, and it's placeholder-grade rather than the product's voice |

---

## Score (lenses, /50)

| Lens | Score /10 | Note |
|---|---|---|
| First impression | 4 | A dashboard, not a companion; the personality is one corner away |
| Hierarchy | 6 | Cards are legible and ranked, but the core action is not first |
| Color voice | 4 | Generic violet accent, no hue tied to the cat's world |
| Type voice | 4 | Split personality (display sans + body sans + mono) with no reason |
| Interaction feel | 7 | Strong controls, states, and recovery copy; hover-only affordance and magic padding cost it |
| **Total** | **25 / 50** | |

The score is low because the *basics* — what a user meets and what they do
first — are not aligned with the product's actual job. The finishing details
(mascot, color, type) can only matter after the arrival and the primary action
are right.

---

## Recommended next moves (impact order)

1. **`/design relayout`** — make Chat the arrival surface (or put the composer on Home). Fix the "core action is one click away" problem first.
2. **`/design voice` + `/design recolor`** — commit to one identity: extend the crayon/ink cat's warmth (warm ginger + ink, humanist type) across the whole product, and retire the generic violet SaaS accent. This directly answers the user's taste reference (Anthropic's hand-drawn, warm, character-first mascot — Kitty's `CrayonCat` is already that kernel, it just doesn't own the shell).
3. **`/design interaction`** — replace hover-only card affordances with a visible rest state.
4. **`/design typeset`** — resolve the display-sans/body-sans/mono split into one voice.

---

## Considered but rejected

| Location | Candidate | Rejected because |
|---|---|---|
| `CrayonCat.tsx` | Replace the crayon cat with a cleaner vector mascot | The crayon cat is the product's strongest, most authored asset; it should own *more* of the surface, not less |
| `globals.css` | Dark "terminal" theme as the identity | The product's voice is warm and hand-drawn; a terminal mono theme is the domain default the user explicitly wants to *leave* |
| `HomeState.tsx` | Remove cards entirely for a minimalist chat | Home's monitoring cards serve a real job (recovery, approvals, deadlines); the fix is arrival + ordering, not amputation |

---

## Verification

**Checked (source-grounded):**
- `page.tsx` / `KittyContext.tsx` — default view is `home` (confirmed arrival is not Chat).
- `CrayonCat.tsx` — four expressive states, hand-drawn crayon/ink style.
- `globals.css` — three themes, `--color-accent: #6557D9` (violet), Inter body / Avenir display.
- `ui.ts` — shared card/type tokens (hairline borders, mono meta).
- `HomeState.tsx` — `itemCard` hover-only border swap on interactive items.
- `KittyThread.tsx` — magic `176`/`140` paddingBottom, generic empty-state copy.
- `StatusBar.tsx` / `HomeState.tsx` — plain-language recovery copy.

**Not verified (no running product / no screenshot):**
- Actual rendered composition at 1440px and iPhone-class widths.
- Color contrast ratios of the violet accent on its surfaces.
- Motion behavior live (corner cat animation).
- Focus order end-to-end through the keyboard.

These are verification gaps, not findings. The next pass should be run against
a booted product to confirm visual and motion claims.

---

## Verdict

**Needs changes** — no `HIGH` accessibility blockers are standing (the keyboard
path and focus rings are genuinely there), but the two `HIGH` composition and
voice findings mean the product is not yet serving its own core job on
arrival. The fix path is relayout first, then voice/recolor/typeset to make
the crayon cat own the whole surface.
