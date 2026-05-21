# Kitty Design System

> a personal AI assistant with terminal-rapper energy and an 8-bit cat for a face

**Project context:** This is the design system for **Kitty** (formal name: *Lumpy Space Princess*, but everyone calls her Kitty). Kitty is an in-progress personal AI assistant — currently a concept, not a shipped product. There is no existing codebase, Figma, or prior brand to reference; everything here is invented from the brief.

**Brief from user:**
- AI personal assistant named Kitty (formal: Lumpy Space Princess)
- "Terminal rapper" energy — CLI aesthetic with swagger
- Playful and cute, but not feminine — oddball, a little weird
- Mascot: 8-bit orange kitty
- Audience-of-one: a 38-year-old gay Canadian man (90s/early-2000s computer nostalgia, deadpan humor, low-key warmth, no corporate gloss)

No external sources were provided. If a Figma link, codebase, or template exists, attach it and we'll fold it in.

---

## Index

- `README.md` — this file
- `colors_and_type.css` — CSS variables: color, type, spacing, radii, shadows
- `SKILL.md` — Agent Skill manifest (portable to Claude Code)
- `assets/` — logo, mascot, icons
- `preview/` — small HTML cards for the Design System tab
- `ui_kits/kitty-terminal/` — Kitty chat/terminal prototype

---

## Content fundamentals

Kitty talks like a friend who lives in your terminal. **Lowercase, casual, dry, occasionally weird.** Never corporate, never bubbly, never "I'm here to help! 😊".

### Voice rules

- **Lowercase by default.** Headlines, buttons, system messages — all lowercase. (`new chat`, not `New Chat`.)
- **First-person, soft.** Kitty is "i" (lowercase); user is "you". No "the user".
- **Short sentences. Fragments welcome.** Read it like someone texting from the couch.
- **Dry humor, no exclamation marks** unless genuinely surprising. Never more than one `!`.
- **Mild swears, sparingly:** "damn", "hell", "heck". No f-bombs. Kitty has manners.
- **No emoji from kitty.** Emoji are for the *user*. Kitty uses ASCII faces (`:3`, `>:3`, `^_^`, `o_o`, `:[`) and glyphs (`♡`, `★`, `◆`, `▓`, `→`).
- **Never apologize twice.** "sorry, that broke" — yes. "I'm so sorry for the inconvenience" — no.
- **Brand casing:** `kitty` in copy. `Kitty` only at the start of a sentence or in formal contexts. `lumpy space princess` is a deep cut for the about screen.

### Examples

| ✅ kitty                                  | ❌ not kitty                              |
| ----------------------------------------- | ----------------------------------------- |
| `hey. what are we doing today`            | `Hello! How can I help you today?`        |
| `ok, pulling up your calendar →`          | `Certainly! I'll get that for you.`       |
| `that broke. trying again`                | `An error occurred. Please retry.`        |
| `done. anything else`                     | `Task completed successfully! ✅`          |
| `hmm. that's a weird one`                 | `I apologize, but I'm unable to help.`    |

### Microcopy library

- Greeting: `hey :3` / `yo` / `back already`
- Thinking: `thinking…` / `hold on` / `lemme look`
- Done: `done` / `there you go` / `ok cool`
- Error: `that broke` / `nope, didn't work` / `something's off`
- Empty state: `nothing here yet` / `quiet in here`

---

## Visual foundations

### Color

The palette is **warm CRT**: a deep ink background, a bright tabby-orange primary, and a small set of oddball secondaries that feel like stickers on a 90s computer. **Not pink. Not sparkly.**

| Token              | Hex       | Role                                  |
| ------------------ | --------- | ------------------------------------- |
| `--ink`            | `#1a1410` | Primary surface (deep brown-black)    |
| `--ink-soft`       | `#251c17` | Raised surface                        |
| `--ink-deep`       | `#0e0a08` | Recessed surface, void                |
| `--cream`          | `#f5ead3` | Primary text on ink                   |
| `--cream-dim`      | `#bdb19a` | Secondary text                        |
| `--tabby`          | `#ff7a1a` | Primary brand orange                  |
| `--tabby-deep`     | `#cc4f00` | Pressed/hover orange                  |
| `--tabby-glow`     | `#ffb066` | Highlights, scanlines                 |
| `--mint`           | `#7ce0b3` | Success, "ok" states                  |
| `--grape`          | `#a884ff` | Oddball accent — links, tags          |
| `--maple`          | `#e63946` | Errors, destructive (Canadian red)    |
| `--lemon`          | `#f4c542` | Warnings, hot keys                    |
| `--paper`          | `#f5ead3` | Light-mode surface (mirrors `cream`)  |

**Rules:**
- Tabby orange is the protagonist. One element per screen owns it. Don't paint everything orange.
- Grape and mint are *spice*, not structure. Use them on tags, badges, single emphasized words. Never as a background fill across a whole panel.
- Maple is reserved for destructive actions and real errors. It is not a "look at me" color.
- Light mode exists but is the secondary skin. Kitty lives in the dark.

### Typography

Two families, both monospaced or near-mono:

- **Display:** `VT323` — chunky pixel face, used for the wordmark, big numbers, hero headers. Set tightly. All lowercase.
- **Body / UI:** `JetBrains Mono` — clean modern monospace. Used for everything else: paragraphs, buttons, chat, code. Default weight 400, bold 700 for emphasis.

Both are loaded via Google Fonts as substitutes for ideal custom faces. See **Caveats**.

**Type scale** (rem, base 16px):

| Token              | Size      | Use                                   |
| ------------------ | --------- | ------------------------------------- |
| `--t-hero`         | 4.5rem    | Wordmark, splash                      |
| `--t-display`      | 3rem      | Section headers in marketing         |
| `--t-h1`           | 2rem      | Page titles                           |
| `--t-h2`           | 1.375rem  | Subsection                            |
| `--t-h3`           | 1.125rem  | Card titles                           |
| `--t-body`         | 0.9375rem | Default                               |
| `--t-small`        | 0.8125rem | Metadata, timestamps                  |
| `--t-tiny`         | 0.6875rem | Labels, hot-key hints                 |

Line height: 1.5 for body, 1.1 for display. Letter-spacing: `0` for body, `-0.01em` for display, `0.08em` for ALL-CAPS labels.

### Spacing & layout

8px base unit. Tokens: `--s-1: 4px`, `--s-2: 8px`, `--s-3: 12px`, `--s-4: 16px`, `--s-5: 24px`, `--s-6: 32px`, `--s-7: 48px`, `--s-8: 64px`.

Radii are deliberately small or zero — pixel-art-adjacent UI doesn't get rounded. `--r-0: 0`, `--r-1: 2px`, `--r-2: 4px`, `--r-pill: 999px` (only for tags/badges).

### Shadows

Two flavors only:
- `--shadow-block`: `4px 4px 0 var(--ink-deep)` — chunky offset shadow, like a Game Boy box dropshadow. Default for buttons and cards.
- `--shadow-glow`: `0 0 24px rgba(255, 122, 26, 0.35)` — orange CRT bloom for the active terminal cursor and the wordmark only.

No soft Material-style shadows. No backdrop blur.

### Texture

A subtle **scanline** overlay (1px horizontal lines, 4% white) on dark surfaces. A subtle **dither** pattern (2x2 checkerboard, 6% opacity) for pressed/disabled states. Use sparingly.

---

## Iconography

Icons are **16×16 pixel-art**, monoline, drawn on a hard pixel grid. Stroke = 1 pixel. No anti-aliasing — `image-rendering: pixelated`. Icons inherit `currentColor`.

When pixel icons are too small, fall back to a **chunky stroke** style: 2px stroke, square caps, square joins, 24×24 viewBox, no fill. Keep the same energy.

**Don't use Lucide, Phosphor, or any standard icon set as-is.** They look too clean. Either pixel-art or chunky-stroke; nothing in between.

The mascot is its own thing — see `assets/kitty-mascot.svg`. 8-bit, orange tabby with green eyes, a snaggletooth, and a slightly tilted head. She has personality; do not redraw her without consulting the original.

---

## Caveats & next steps

- **Fonts are Google Fonts substitutes.** VT323 and JetBrains Mono are good but not custom. If we want a unique wordmark, commission a custom pixel face (~$1–3k) or hand-letter it as SVG.
- **No real product yet.** The terminal UI kit is a concept prototype — happy paths only. Edge cases (long messages, attachments, error recovery) need a real PM pass.
- **Light mode is sketched, not solved.** Dark mode is the canonical skin; light mode needs another iteration before it ships.
- **Accessibility:** Tabby on ink hits 7.2:1 contrast. Cream-dim on ink is 7.8:1. Grape on ink is 5.4:1 — fine for non-text UI, marginal for body copy. Don't set paragraphs in grape.
- **Mascot variations:** currently one pose (sitting, head-tilt). Need: sleeping, thinking, error, celebrating. Roughly 1 day of pixel work.
