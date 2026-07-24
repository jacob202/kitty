# kitty design system — agent skill

This file makes the kitty design system portable to Claude Code or other agents.

## When to use

Use this skill whenever you're building anything for **kitty** (the personal AI assistant, formal name *lumpy space princess*) — chat UI, marketing pages, dashboards, mobile shells, error screens. If the project says "kitty", load this skill before opening other context.

## What kitty is

A personal AI assistant with **terminal-rapper** energy — CLI aesthetic, swagger, dry humor. Mascot is an 8-bit orange tabby. Audience is one specific user (a 38yo gay Canadian dude with computer-nostalgia taste); design accordingly: low-key, deadpan, never bubbly, never corporate.

## Files in this kit

- `README.md` — full brand book (voice, color, type, icons, rules)
- `colors_and_type.css` — drop-in CSS variables (colors, type, spacing, radii, shadows)
- `assets/kitty-mascot.svg` — full sitting mascot (32×32 pixel grid, render with `image-rendering: pixelated`)
- `assets/kitty-mark.svg` — head-only app icon
- `assets/kitty-wordmark.svg` — `$ kitty` wordmark with blinking caret
- `preview/*.html` — reference cards for each subsystem
- `ui_kits/kitty-terminal/` — canonical chat/terminal UI

## Quick checklist

Before shipping any kitty surface, verify:

- [ ] All copy is **lowercase** (headlines, buttons, tooltips). One stray "Sign In" and the spell breaks.
- [ ] Kitty refers to herself as `i`, the user as `you`. No "the user".
- [ ] No emoji from kitty. ASCII faces (`:3` `>:3` `^_^` `o_o` `:[`) and unicode glyphs (`♡ ★ ◆ ▓ →`) only.
- [ ] Tabby orange (`#ff7a1a`) is used **once per screen** as the protagonist. Don't paint the page orange.
- [ ] Spice colors (mint, grape, maple, lemon) are stickers — never panel fills.
- [ ] Radii ≤ 4px on everything except tags (`--r-pill`).
- [ ] Shadows are `4px 4px 0` offset, not soft Material drops.
- [ ] Pixel art SVGs have `image-rendering: pixelated` on the `<img>` or container.
- [ ] Type: VT323 for display; JetBrains Mono for body. No third family.
- [ ] No exclamation points in product copy unless something is genuinely surprising. Never `!!`.

## Voice cheatsheet

Greeting: `hey :3` · `yo` · `back already` · `oh hi`
Thinking: `thinking…` · `hold on` · `lemme look`
Done: `done` · `there you go` · `ok cool`
Error: `that broke` · `nope, didn't work` · `something's off`
Empty: `nothing here yet` · `quiet in here`
Refusal: `nah, can't do that one` · `that's outside my zone`

## Don'ts

- Don't redraw the mascot from scratch. Reuse the SVG; new poses get added to `assets/` not improvised.
- Don't use Lucide / Phosphor / Heroicons as-is — they're too clean. Pixel-art (16×16) or chunky-stroke (24×24, 2px square caps) only.
- Don't add gradients or backdrop-blur. We're a CRT, not a SaaS landing page.
- Don't introduce a third color outside the token set. If you need a new color, propose it to the user first.
- Don't capitalize the brand mid-sentence. `kitty` lowercase always except sentence start.
