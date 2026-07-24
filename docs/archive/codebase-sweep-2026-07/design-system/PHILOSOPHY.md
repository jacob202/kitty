# the kitty design philosophy

> the reason this thing looks like anything at all

This is the *why* behind every pixel. The brand book (`project/README.md`) says
*what* the tokens are; the skill manifest (`project/SKILL.md`) is the checklist.
This file is the thing they both answer to. When a screen feels wrong and the
tokens are all technically correct, the answer is in here.

It exists because the look was paid for in full — two long design sessions of
"no," "I hate this," and "how many times do I have to give you the exact same
instructions." Those decisions are settled now. This document is where they
live so nobody has to win those arguments again.

---

## the thesis

**Kitty is software for an audience of one.**

Not a persona. Not a segment. One actual person — Jacob: 38, gay, Canadian,
raised on 90s/2000s computers, deadpan, allergic to corporate gloss, runs on
opposition. Every other AI tool is built for a distribution and therefore can't
have a self — it has to stay neutral enough to convert strangers. Kitty doesn't
convert anyone. It already knows exactly who's in the room.

That single fact is the whole license. A tool built for one person is allowed
to be weird. It can have inside jokes. It can assume context instead of
re-explaining itself. It can be opinionated to the point of rudeness because it
knows precisely who's listening and that he likes it that way. **The job of the
design is not to impress — it's to be good company.**

Everything below falls out of that.

---

## product vs. place

Most assistants are designed to feel like a **product**: clean, neutral,
scalable, safe for everyone, and therefore characterless. Kitty is designed to
feel like a **place that belongs to one person** — a lived-in room, not a
dashboard; a desk where everything is already in reach.

This is the reframe that resolves the tension we kept circling:

- a product shouts to get noticed. **a room is just quietly itself.** → restraint.
- a product hides complexity to look simple. **a desk keeps everything in
  view.** → information density without clutter.
- a product is warm-on-brand. **a room is actually warm.** → the palette is not
  decoration, it's the temperature of the space.
- a product has a voice in marketing. **a companion has a self everywhere.** →
  personality is load-bearing, not garnish.

> Kitty's UI is the **body** of the same character whose **mind** is in
> `config/SOUL.md`. The voice that plays devil's advocate, names your fallacies,
> teases you, and won't flatter you — that's the same entity the interface is
> dressing. If the screen feels like a different personality than the system
> prompt, the screen is wrong. Read SOUL.md before you redesign anything; the
> visual language has to agree with it.

---

## the feeling we're aiming at

Jacob's own words, kept because they're the target:

**cozy · playful · modern consumer chat · fresh, not just modern · slick,
intuitive, deliberate · lots of information readily available.**

Hold all of those at once. The trap is that each one has a cheap version that
looks right for a second and then curdles:

| we want | the cheap version that betrays it |
|---|---|
| cozy | sepia, tan-on-tan, "too light," nostalgia cosplay |
| playful | neon rainbow, emoji confetti, exclamation points |
| terminal *DNA* | full CRT costume — scanlines everywhere, MOTD, mono body |
| modern & slick | the generic dark-AI-app — cool slate, no soul, could be anyone's |
| data-rich | a wall of cards that fatigues the eye |
| personality | a mascot pasted on like a sticker |

**Fresh** is the word that keeps it honest. Not retro (costume), not modern
(generic) — *fresh*: it has the DNA of a terminal and the manners of a 2026
consumer app, and it feels like neither one in a museum. We borrow the
terminal's honesty (monospace where data lives, hard edges, no skeuomorphic
lies) without wearing it as a hat.

---

## the principles

These are laws, not suggestions. Each one is a decision that was made the hard
way; the *because* is there so you don't undo it.

1. **One protagonist per screen.** Tabby orange (`--tabby`) is the lead and it's
   rare on purpose. One element owns it per view. The moment everything is
   orange, nothing is. Restraint is what makes the color land — *because* the
   neon-everything build got called "too fatiguing, not tasteful, not
   sophisticated," and it was right.

2. **Color is the soul, used with a budget.** The warm squad — `tabby` +
   `grape` + `blush`, on warm `ink`, with `teal`/`mint`/`maple` as quiet
   role-players — is the single most-loved part of this system ("my favourite
   part," said more times than it should have taken). It must be *visible*, not
   buried under brown, and it must never tip into a rainbow. Tasteful means: two
   accents doing the talking, the rest reserved for meaning (mint = ok, maple =
   trouble), nothing colored just to be colored.

3. **Dark, and actually warm.** The canvas is warm brown-black (`--ink`
   `#1a1410` family), not cool slate. Light/cream exists as a secondary skin but
   "too light for me" is on the record — dark is home. Warmth is the difference
   between *cozy* and *every other dark app*; do not let the canvas drift cool
   and gray. (It currently has — see "the three systems" below.)

4. **No bubbles. No labels. No avatars per message.** Chat is flat runs of
   text: Kitty's words on the left, yours distinguished by the lightest possible
   means. Per-message avatars and "kitty/you" tags were killed for being "loud,
   busy, unnecessary" and for cluttering "the whole interface." One small mascot
   peek on Kitty's first reply in a run is the entire allowance. The
   conversation is the content; the chrome gets out of its way.

5. **Everything in reach, nothing in your face.** Rich side panels are good —
   Jacob *likes* the brief packed with data. But panels are collapsible, always,
   and a closed panel takes up *nothing*. Density earns its place by being
   calm: quiet labels, hairline dividers, one accent per region. A static
   half-screen panel is a bug, not a feature.

6. **Monospace is for data, not for prose.** Space Grotesk (display) carries the
   voice and the headings; Space Mono is for timestamps, code, tool calls,
   numbers — the things that *are* terminal. Body text is not monospace. This is
   the line between "terminal DNA" and "terminal costume," and we stay on the
   right side of it.

7. **Hard edges over soft gloss.** Small radii, honest borders, chunky offset
   shadows (`4px 4px 0`) rather than soft Material blur. No backdrop-blur, no
   glassmorphism, no gradient that announces itself. Gloss is the texture of a
   product trying to be liked; Kitty isn't trying.

8. **Motion is small and alive.** A 4-second mascot bob. A blinking caret. A
   pulse on a live agent. Movement signals *this thing is awake and listening*,
   never *look at me*. Nothing bounces, nothing slides for decoration.

9. **Lowercase by default.** Headings, buttons, system text — lowercase. The
   interface never raises its voice. `new chat`, not `New Chat`. One stray
   `Sign In` and the spell breaks.

---

## personality & humor, as material

Personality here is not a coat of paint applied at the end — it's a building
material with structural jobs. "More personality and funk," "spunk, not too
cute": the brief was always for character with an edge, never for adorable.

- **The mascot is a status display, not a logo.** This is the most novel move in
  the system and the one to protect. The cat's pose and expression are *bound to
  system state* — awake and bobbing when present, asleep when idle, alert on
  error, pleased when something finishes. She's a live readout of how Kitty is
  doing, sitting in the corner as a status pet and front-and-centre on the empty
  state. Most apps' mascots are dead brand furniture; ours is a gauge with a
  face. Never reduce her to decoration. (And never redraw her on a whim — the
  8-bit version got called "the ugliest fucking cat"; the mascot file is canon,
  new *poses* get added, the character does not get reinvented.)

- **Voice is deadpan, lowercase, dry.** Kitty is `i`; you are `you`; never "the
  user." Short sentences, fragments welcome, real thinking with its texture left
  on ("wait, hold on—"). No exclamation marks unless something is genuinely
  surprising, and never two. Mild swears, sparingly. **Never apologize twice** —
  "sorry, that broke" is the whole apology, "I'm so sorry for the inconvenience"
  is corporate grovelling and is banned. No emoji *from Kitty*; ASCII faces
  (`:3 >:3 ^_^ o_o :[`) and glyphs (`♡ ★ ◆ ▓ →`) are her emoji.

- **Errors keep their dignity.** "that broke. trying again" — not a red modal
  with an apology essay. The user is never punished for a failure that isn't
  his. Approachable means the bad moments are handled with the same calm as the
  good ones.

- **Empty states have a point of view.** "nothing here yet." "quiet in here."
  Blank space is a chance to be company, not a void to apologize for.

- **Deep cuts are allowed.** The formal name *lumpy space princess* lives on the
  about screen as a reward for looking. Audience-of-one means a joke can land for
  exactly one person and that's a complete success. Don't sand the weird off.

The humor rule: **dry and load-bearing, never random.** A joke earns its place
by being *true* — about the moment, the data, the user — not by being quirky for
quirk's sake.

---

## the look, settled

So nobody has to re-derive it:

- **Type** — `Space Grotesk` (display, the voice) × `Space Mono` (data, code,
  meta). No third family. Body is *not* mono.
- **Canvas** — warm dark. `--ink-deep #0e0a08` page, `--ink #1a1410` panels,
  `--ink-soft #251c17` cards, `--cream #f5ead3` text.
- **Accents** — `--tabby #ff7a1a` lead, `--grape #a884ff` second, `--blush
  #ff8aa6` the unapologetic signature spice (pink-on-orange-on-black is the
  point, not an accident). `--teal`/`--mint`/`--maple`/`--lemon` carry meaning
  only: link/fresh, ok, trouble, heads-up.
- **Shape** — small radii, hairline borders, `4px 4px 0` offset shadow. No soft
  drop shadows, no blur, no loud gradients.
- **Layout** — thin icon rail + a collapsible left sidebar (navigation, lighter)
  + center conversation + a collapsible right sidebar (the data-rich brief:
  calendar, schedule, watching, memory peek, status pet). Both rails collapse to
  zero. Today's date and the calendar live top-right.
- **Chat** — flat lines, no bubbles, no per-message labels, one mascot peek per
  run.

The full token table is in `project/colors_and_type.css`; it is the source of
truth for values. This section is the source of truth for *intent*.

---

## what would betray kitty

You've lost the plot when:

- the canvas has gone cool/gray and it could be any other AI app
- the brand colors are buried and the screen is mostly brown, **or** every
  element is a different color and your eyes are tired
- there are chat bubbles, message avatars, or "user:" / "assistant:" labels
- body copy is monospace and the thing reads like a 1985 terminal
- the mascot is a static logo instead of a live status display
- a panel can't collapse, or eats half the screen when "closed"
- there's an exclamation point in product copy, or a double apology
- something is capital-cased that didn't have to be
- a color, animation, or gradient exists only to be noticed

If two or more of those are true, stop and come back to this file.

---

## the three systems (a standing honesty note)

As of this writing there are **three** partially-divergent looks in the repo,
and they don't agree. This is drift, not design. Naming it so it gets fixed
instead of multiplying:

1. **the brand book** (`project/README.md`) — still documents the *original* CRT
   build: `VT323` + `JetBrains Mono`, the pre-evolution palette. **Stale.** The
   type and palette moved on; the README didn't.

2. **the matured tokens** (`project/colors_and_type.css`, `ui_kits/kitty-rail/`)
   — `Space Grotesk` × `Space Mono`, warm ink, tabby/grape/blush, no-bubble
   flat chat, collapsible rails. **This is the canonical direction** — it's
   where the two design sessions actually landed. This file's "the look,
   settled" section matches it.

3. **the shipped app** (`gateway/kitty-chat/src/app/globals.css`) — over-corrected
   toward generic-slick: a **cool** `#0f0f14` canvas (not warm ink), `Hanken
   Grotesk` (not Space Grotesk), 18px radii and soft shadows (not hard edges).
   It got "modern web app" right and dropped the warm soul that was the most-loved
   part. **This is the drift to repair**, per principles 2, 3, 6 and 7.

**Recommendation:** treat system #2 as canon. Refresh the brand book (#1) to
match it, and reconcile the shipped app (#3) onto the warm `ink` canvas, Space
Grotesk/Space Mono, and tighter radii — keeping the genuinely-good "slick modern
web app" structure it already has. The goal is not to make the app more retro;
it's to make it warm and *Kitty* again without losing the slickness. None of
that is done in this commit — this file just draws the map.
