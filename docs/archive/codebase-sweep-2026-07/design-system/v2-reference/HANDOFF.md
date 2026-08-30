# Kitty — Claude Code Handoff

## read first

`KITTY.md` — the full brief. Voice, the four states, cat philosophy, type rules, do/don't. Read it before touching anything.

## what's here

```
handoff/
├── README.md               ← you are here
├── KITTY.md                ← brand brief (read first)
├── tokens.css              ← day + night CSS custom properties
│
├── screenshot-day.png      ← pixel reference, day (manila paper) theme
├── screenshot-night.png    ← pixel reference, night (chalkboard) theme
│
├── Kitty UI v2.dc.html     ← interactive prototype — open in browser
├── Kitty Reimagined.dc.html← full brand direction doc — open in browser
├── support.js              ← DC runtime (required to open the .dc.html files)
│
├── cat-assets/
│   ├── kid-cat.svg         ← THE crayon cat base. use this. don't redraw.
│   ├── state-idle.svg      ← four state poses (flat, from prior iteration)
│   ├── state-working.svg
│   ├── state-done.svg
│   ├── state-broke.svg
│   ├── kitty-mascot.svg    ← original 8-bit mascot (reference only)
│   ├── kitty-mark.svg      ← logo mark (reference)
│   └── 8bit-*.svg          ← original 8-bit state frames (reference only)
│
└── ds/
    ├── colors_and_type.css ← original design system tokens (warm-CRT canon)
    ├── openwebui-kitty.css ← openwebui theme skin
    └── README.md           ← original design system brief
```

## opening the prototype

Both `.dc.html` files need `support.js` in the same folder. Open `Kitty UI v2.dc.html` directly in a browser — no build step.

## which tokens to use

`tokens.css` (root of this folder) is the **new canonical skin** — the reimagined crayon/paper palette. It overrides the original warm-CRT system the user deliberately moved away from. `ds/colors_and_type.css` is the old canon, kept for reference.

## layout spec (from the prototype)

| zone | width | notes |
|---|---|---|
| rail | ~94px | icon + label, vertical nav, cat mark top, theme + avatar bottom |
| sidebar | ~268px | new chat, search, grouped history (pinned/today/yesterday/earlier) |
| main | flex:1 | topbar 58px, messages scrollable, input bar fixed bottom |
| corner cat | fixed, bottom-right | always visible, animates with state |

## the cat — do not touch

- use `kid-cat.svg` as the base SVG for the crayon cat
- the wobbly displacement filter (`feDisplacementMap`, seed 7) is load-bearing — it IS the aesthetic
- fills spill outside the outline on purpose
- `--cat-ginger` for fill, `--cat-outline` for stroke — see `tokens.css`
- she is NOT the primary color, NOT a logo, NOT a sticker
- four states: `._. idle` / `o_o working` / `^_^ done` / `:[ broke`
- the face ASCII changes, the pose/animation changes — the color doesn't

## tell Claude Code

> "Read README.md and KITTY.md first. Match screenshot-day.png and screenshot-night.png exactly — those are the pixel reference. tokens.css has both skins. The cat is in cat-assets/kid-cat.svg — don't redraw her, use the SVG with the displacement filter as shown in the prototype."
