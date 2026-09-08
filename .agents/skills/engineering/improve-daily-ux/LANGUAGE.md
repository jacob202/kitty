# Language

Shared vocabulary for every suggestion this skill makes. Use these terms exactly —
don't substitute "UI," "frontend," "polish," or "component." Consistent language is
the whole point.

## Terms

**Surface**
Anything the user looks at and acts on — a screen, panel, card, thread, or input.
Deliberately scale-agnostic: applies to the whole `WorkView` or a single
`BuilderProposalCard`.
_Avoid_: page, screen, component (component is an implementation unit, not what the
user experiences).

**State**
One of the conditions a surface can be in while data is in flight or unavailable.
Kitty's canonical set, from `AsyncState`: **loading**, **empty**, **degraded**,
**unavailable**, **stale**, **error**, **retrying**, **partial**, **forbidden**.
Every async surface owes the user the right state.
_Avoid_: status (overloaded with `StatusBadge`'s task vocabulary).

**State coverage**
Whether a surface renders the correct `AsyncState` for every state it can actually
be in. A surface that can be degraded but only handles loading and empty has a
**coverage gap**.

**Coverage gap** _(the defect)_
A state the surface can be in but doesn't render — showing a blank pane, an eternal
spinner, or nothing where the user is owed a loading / empty / error / degraded /
stale signal.

**Honest state**
A state that tells the truth about the data. "Couldn't load" (unavailable) is honest;
rendering the same gap as "nothing here" (empty) is not. Honesty means the user can
distinguish *absent* from *unreachable*.
_Avoid_: accurate (too weak — honesty is about not lying by omission).

**Optimistic lie** _(the defect)_
Rendering unavailable or failed data as empty / zero / blank to "look cleaner." It
hides evidence from the user — the surface-level twin of the silent default that
`harden-codebase` hunts.

**Copy**
The words on a surface: titles, messages, button labels, error text. Good copy names
the cause and the next step.
_Avoid_: text, content, messaging.

**Dead end**
Copy or a state that tells the user something went wrong but offers no cause and no
next step — "Error." with no retry, no explanation, no path forward.

**Feedback**
What the user gets back after they act: confirmation, progress, a retrying state, or
silence. A surface that accepts an action and shows nothing has a **feedback gap**.

**Perceived latency**
How long the wait *feels*, which is not the same as how long it is. A skeleton or
`retrying` state makes a 2s wait feel shorter than a blank pane makes a 200ms wait.

**Recovery affordance**
The control the surface gives the user to get unstuck without reloading the app —
`AsyncState`'s retry / reconnect buttons. A failure with no recovery affordance is a
dead end even if the copy is honest.

**Daily-touch frequency**
How many times a day the user actually hits this surface. The multiplier in the
daily-touch test.

**Friction cost**
What one occurrence of the gap costs the user — confusion, a wasted reload, a lost
action, a moment of "is it broken or is it me?"

## Principles

- **The daily-touch test.** Leverage = daily-touch frequency × friction cost. A small
  papercut on a surface hit 50×/day outranks a big one hit once a month. Rank
  candidates by this, not by severity alone.
- **Every async surface owes the user a state.** If a surface can be loading, empty,
  error, degraded, or stale, it must render the right `AsyncState` for each. A
  coverage gap is the defect.
- **Honest states over optimistic ones.** Never render unavailable data as empty or
  zero. "Couldn't load" ≠ "nothing here." The canonical `AsyncState` already
  distinguishes them; the defect is surfaces that don't use it.
- **Copy names the cause and the next step.** Not "Error." Not a raw exception. What
  happened, and what the user can do — ideally with a recovery affordance beside it.
- **Use the canonical surface, don't fork it.** If `AsyncState` covers the state, the
  fix is to use it. One canonical vocabulary across surfaces is the point; a parallel
  state component is a regression.

## Relationships

- A **Surface** is in exactly one **State** at a time; **state coverage** is whether
  it renders the right one for each state it can be in.
- A **coverage gap** or an **optimistic lie** is the defect; an **honest state** with
  good **copy** and a **recovery affordance** is the fix.
- **Perceived latency** is managed by feedback (skeleton / retrying), not by making
  the operation faster — that's a different skill's job.
- **Daily-touch frequency** × **friction cost** ranks candidates by leverage.

## Rejected framings

- **"Polish" as a goal**: too vague and invites redesign. We mean removing a specific
  coverage gap or optimistic lie on a specific surface, ranked by the daily-touch
  test.
- **"UX" as visual design**: this skill is not a redesign or an aesthetic pass. It's
  about whether the surface tells the truth and helps the user across its states.
- **"Empty state" as a single thing**: Kitty distinguishes empty / unavailable /
  degraded / stale / partial. Collapsing them into one "empty" is itself an
  optimistic lie.
- **Treating every spinner as a defect**: a loading state is correct while data is
  genuinely in flight. The defect is a spinner that never resolves, or a loading
  state where an error / degraded state is owed.
