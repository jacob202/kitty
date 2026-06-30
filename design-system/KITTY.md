# KITTY — brand & engineering brief

> one-page reference. keep it open when building.

---

## what kitty is

Kitty is a **personal AI assistant for an audience of one.** Not a product, not a chatbot — a calm command center with a kiss of magic. Built for a 38-year-old who knows what he wants, doesn't need hand-holding, and will notice immediately if it goes corporate.

**The mascot is an instrument, not a portrait.**
Her pose reads system state. She is a gauge with a face — not a logo, not a sticker, not a vibe. Her expression *means something*.

---

## the four states (non-negotiable)

| state | face | meaning |
|---|---|---|
| idle | `._.` | awake, waiting. she blinks. don't bother her. |
| working | `o_o` | heads-down. something is running. |
| done | `^_^` | pleased with herself. |
| broke | `:[` | something went sideways. she owns it, doesn't panic. |

The cat's animation and pose change with state. Never show `^_^` while working. Never show `o_o` at idle. The state is load-bearing.

---

## the mascot — how to draw her

She is a crayon cat drawn by a six-year-old, allegedly.

- **outline**: wobbly stroke (SVG `feDisplacementMap`, seed 7, scale ~5). never clean.
- **fill**: ginger (`--cat-ginger`) that **spills outside the outline** — color outside the lines, on purpose. use a heavier displacement (scale ~8) on fills, lighter on outline.
- **eye**: green (`--cat-green`). one visible eye (3/4 pose).
- **nose / inner ear / cheek**: pink (`--cat-pink`). small blush dot on cheek.
- **outline color**: `--cat-outline` — dark brown on day, chalk-cream on night.
- **do not clean her up.** the wobble is the point. she is not a polished mascot — the ugly is intentional and charming.

The cat's color is always `--cat-ginger`. She is never blue, never primary-colored, never the same as the UI accent. She is her own thing.

---

## voice

Lowercase. Dry. Casual. Never corporate. Kitty talks like a friend who lives in your terminal.

### rules
- **lowercase by default.** headlines, buttons, toasts, empty states — all lowercase.
- **short sentences.** fragments welcome. read it like a text from the couch.
- **no exclamation marks** unless genuinely surprising. never more than one.
- **no emoji from kitty.** she uses ASCII faces and glyphs: `♡ ★ → ◆`.
- **never apologize twice.** "sorry, that broke" — yes. "i'm so sorry for the inconvenience" — no.

### table of good/bad

| ✅ kitty | ❌ not kitty |
|---|---|
| `hey. what are we doing today` | `Hello! How can I help you?` |
| `on it →` | `Certainly! Right away.` |
| `that broke. trying again` | `An error occurred. Please retry.` |
| `done. anything else` | `Task completed successfully ✅` |
| `hmm. that's a weird one` | `I apologize, but I'm unable to help with that.` |

### microcopy
- greeting: `hey :3` / `hey.` / `back already`
- thinking: `thinking…` / `hold on` / `lemme look`
- done: `done` / `there you go` / `ok cool`
- error: `that broke` / `nope, didn't work` / `something's off`
- empty: `nothing here yet` / `quiet in here`

---

## visual system

### palette
All tokens in `tokens.css`. Two skins — apply via `data-theme="day"` or `data-theme="night"` on the root.

- **day**: warm manila paper (`--bg: #F3EAD6`). crayon accents on cream.
- **night**: deep chalkboard slate (`--bg: #272D2B`). chalk-pastel accents.
- **primary**: soft cornflower blue (`--primary`). one element per screen owns it.
- **cat ginger** (`--cat-ginger`) is NOT the primary. she is her own color. don't reuse it for buttons.
- **`--c-red`** = errors and pinned only. not a "look at me" color.
- **`--c-green`** = done, ok, synced.

### type
- `--font-display` (Bricolage Grotesque) — wordmark, hero headers, section titles. set tightly. all lowercase.
- `--font-body` (Hanken Grotesk) — all UI: buttons, chat, labels, paragraphs.
- `--font-mono` (JetBrains Mono) — **only** for: hotkeys, timestamps, state badges, system echoes. not for body copy. it's a wink at the terminal past, not a design statement.

### layout
- **rail** (~94px): icon + label, vertical stacked nav. kitty mark at top, theme + avatar at bottom.
- **sidebar** (~268px): new chat (top), search, grouped history (pinned / today / yesterday / earlier). dense: title + preview + timestamp per row. hand-drawn crayon underline per section.
- **main**: topbar (wordmark + state chip + controls), messages, input bar.
- **corner cat**: fixed, bottom-right, always visible, animates with state.

### whimsy (important)
- every stroke that can wobble, wobbles. SVG `feDisplacementMap` on icons, underlines, cat.
- section underlines are hand-drawn SVG paths, one per group, different crayon color per section.
- suggestion chips are slightly rotated "stickers."
- subtle paper grain overlay (SVG `feTurbulence`, ~5% opacity, `mix-blend-mode: multiply` on day / `screen` on night).
- sparkles (`★`) pop near the corner cat on done / task complete.

---

## do / don't

| do | don't |
|---|---|
| lowercase everything | Capitalize UI text |
| use `--cat-ginger` only for the cat | recolor the cat to match the accent |
| embrace the wobbly SVG strokes | clean up the mascot drawing |
| one primary-colored element per screen | paint everything blue |
| keep the four states meaningful | show idle face while working |
| use `--font-mono` for hotkeys + echoes only | set body copy in mono |
| paper grain subtle (≤6% opacity) | crank the grain until it's visible at a glance |
| personality: confident, dry, a little weird | bubbly, apologetic, corporate |

---

## prototype reference

- `Kitty UI v2.dc.html` — interactive prototype. live palette, chat, cat states, day/night flip.
- `Kitty Reimagined.dc.html` — full brand direction: palette swatches, type specimens, mascot philosophy, handoff notes.
- `tokens.css` — this file's companion. paste into your project root or design-tokens layer.
- `_cats/` — existing cat SVG states (pre-redesign; use as pose reference, not final art).
- `assets/mascot/kid-cat.svg` — the crayon cat base SVG.

---

*audience of one. build accordingly.*
