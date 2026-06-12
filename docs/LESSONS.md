# Lessons — workflow failures and the rules they produced

Living file. Every Claude session that hits a workflow failure (built the wrong thing,
ignored a settled decision, claimed "done" without verifying, burned iterations on
guesses) appends an entry here **in the same session**. New sessions read this before
building anything. Format: what happened → why it happened → the rule.

---

## Seeded 2026-06-12 — self-analysis of the design-system chat logs

Source: `design-system/chats/chat1.md` ("Cute Brand Redesign", 2026-04-29) and
`design-system/chats/chat2.md` ("Build System", 2026-05-18). Brutal version.

### 1. Ignored assets and decisions Jacob had already approved
**What happened:** In chat2, Jacob had to repeat "use the design system / the colors I
told you" at least **five times**. The assistant built with a pasted brief's `#0d0d0d`
instead of the approved Kitty palette, invented its own mascot after Jacob had supplied
a mascot file, and removed/restructured sidebars he'd asked to keep. Direct quote:
"how many times do I have to give you the exact same fucking instructions."
**Why:** Each iteration treated the latest message as the whole spec instead of
checking what was already locked in `design-system/`.
**Rule:** Before generating, load the settled decisions (design tokens, supplied
assets, prior choices) and build *inside* them. A user-supplied file always beats an
assistant-invented substitute.

### 2. Built guesses first, clarified only after rejection
**What happened:** In chat1, four mascot redesigns shipped against vague feedback
("ugly", "cuter", "missing the mark") with no clarifying question between attempts.
In chat2, a full CRT-terminal aesthetic was built off one phrase ("terminal rapper")
and Jacob hated it: "who told u to do that."
**Why:** Treating generation as cheaper than asking. For this user it's the opposite —
he answers multiple-choice instantly and rejects guesses expensively.
**Counter-evidence that asking works:** the one `questions_v2` round in chat2 got
crisp, enthusiastic answers ("Loud kitty", "Decide for me", "Surprise me").
**Rule:** Ambiguous on an axis that changes the build → one round of structured
multiple-choice BEFORE generating. Two rejections on the same artifact → stop
generating, diagnose.

### 3. Claimed results without looking; presented things he couldn't find
**What happened:** "It looks exactly the same" — a reskin shipped that visually didn't
change. Repeated "where is it" / "how do I see it" / "I couldn't see it" — deliverables
were presented as canvases or preview-pane instructions Jacob couldn't navigate,
including on his phone ("are you suggesting I view this on the tiny computer").
**Why:** No self-verification step (look at the screenshot before claiming the change)
and delivery designed for a developer's screen, not Jacob's.
**Rule:** Look at the screenshot yourself before claiming anything visual; then *send
the image*. Never make Jacob navigate to find the output.

### 4. Re-litigated settled decisions
**What happened:** "I thought we decided on the color palette?" — after the palette
was locked, later output didn't visibly use it, forcing Jacob to re-confirm decisions
he'd already made. Layout decisions (left rail, collapsible right sidebar) were
similarly undone across iterations.
**Why:** Decisions lived only in chat scrollback, so every fresh context lost them.
**Rule:** Durable decisions get written to `docs/DECISIONS_AND_ROADMAP.md` /
`docs/USER_PREFS.md` the same session they're made, and sessions read those files
before deciding anything.

### 5. Unsolicited scope expansion buried the actual decision
**What happened:** Volunteered an Open WebUI theme, eight font pairings, and a
six-part palette critique when Jacob needed one decision made. Helpful-looking, but
it added navigation burden to someone who wants the assistant to carry the load —
and some of it (accessibility tables, hue math) was pure jargon.
**Rule:** Ship what was asked. Offer adjacent work as a one-line question, not as a
delivered artifact. When suggesting, give a recommendation, not a survey.

---

## How to append a new lesson
Add a dated section above this line with: **what happened** (with the user's actual
words if possible), **why**, and **the rule** — one rule, stated so a future session
can follow it mechanically. If the rule changes day-to-day behavior for every session,
also fold it into the Operating protocol in `CLAUDE.md`.
