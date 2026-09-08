---
name: improve-daily-ux
description: Find the highest-leverage user-experience gaps in the surfaces people touch every day — loading, empty, error, degraded, and stale states, perceived latency, confusing copy, and inconsistent feedback. Grounded in Kitty's canonical AsyncState 9-state surface. Use when the user wants to improve day-to-day experience, polish the UI, fix what the user sees when something loads or fails, reduce friction, or prioritize customer-experience-facing work. The user-facing sibling of improve-codebase-architecture (shape) and harden-codebase (runtime failure): this skill owns what the user actually sees and feels.
---

# Improve Daily UX

Surface **daily-touch friction** — the gaps in what the user sees and feels on the
surfaces they hit every day. The aim is a consistent, honest, low-friction
experience across loading / empty / error / degraded states. This is the
user-facing sibling of `improve-codebase-architecture` (internal shape) and
`harden-codebase` (runtime failure behaviour): those ask *is it built / does it
fail right?*; this one asks *what does the user see, and does it help them?*

## Glossary

Use these terms exactly in every suggestion. Consistent language is the point —
don't drift into "UI," "frontend," or "polish." The canonical definitions live in
[LANGUAGE.md](LANGUAGE.md), injected below; the "Key principles" summary follows.

!`cat "${COMMANDCODE_SKILL_DIR}/LANGUAGE.md"`

Key principles (see LANGUAGE.md for full definitions):

- **The daily-touch test**: how many times a day does the user hit this surface, and
  how much does the friction cost each time? Leverage = frequency × cost. A small
  papercut on a surface hit 50×/day outranks a big one hit once a month.
- **Every async surface owes the user a state.** Loading, empty, error, degraded,
  stale — if a surface can be in one of these and shows nothing (or a spinner
  forever, or a blank pane), that's the defect.
- **Honest states over optimistic ones.** Never render unavailable data as empty or
  zero. "Couldn't load" ≠ "nothing here." Kitty's `AsyncState` already distinguishes
  them — the defect is surfaces that don't use it.
- **Copy tells the user what happened and what to do next.** Not "Error." Not a raw
  exception. A cause and a next step.

This skill is _informed_ by the project's actual surfaces. Kitty already has a
canonical state component and user-actionable error helpers — don't invent new
patterns when the canonical one isn't being used.

## Kitty grounding (read first)

Before exploring, read:

| Doc / file | Purpose |
|-----|---------|
| `gateway/kitty-chat/src/components/ui/AsyncState.tsx` | The canonical 9-state surface: loading / empty / degraded / unavailable / stale / error / retrying / partial / forbidden. The reference every async view should match. |
| `gateway/kitty-chat/src/components/ui/StatusBadge.tsx` | Canonical status vocabulary (working / done / failed / …) |
| `docs/ARCHITECTURE.md` | Live stack, the frontend package layout, what surfaces exist |
| `gateway/llm_client.py` → `describe_chain_exhaustion` | The existing pattern for turning raw provider errors into user-actionable messages |
| `AGENTS.md` | The fail-loud directive — UX is where "loud" becomes "honest and actionable" for the user |

**Domain vocabulary:** use names from `gateway/kitty-chat/src/` — e.g. `AsyncState`,
`KittyThread`, `WorkView`, `BuilderProposalCard`, `InputBar`, the `useKittyState`
animation FSM — not generic "the component" or "the page."

**Recorded decisions:** `docs/adr/` and `docs/DECISIONS.md` are load-bearing. When a
new rejection deserves permanence, offer an ADR using
[ADR-FORMAT.md](../improve-codebase-architecture/ADR-FORMAT.md) (shared).

## Failure modes to avoid

- **Redesigning instead of de-frictioning.** This skill is not a visual redesign or a
  component rewrite. Find the friction in the existing surface and propose the
  smallest change that removes it. Big rewrites belong in a design doc, not here.
- **Polishing the rarely-touched.** Apply the daily-touch test first. A gorgeous
  empty state on a screen nobody visits is waste.
- **Optimistic lying.** Never propose rendering unavailable data as empty/zero to
  "look cleaner." That hides evidence from the user — the same defect
  `harden-codebase` hunts, but on the surface.
- **Inventing a new state component.** If `AsyncState` already covers the state, the
  fix is to *use it*, not to build a parallel one. One canonical surface is the point.
- **Confusing copy with causation.** "Something went wrong" is not a fix. The user
  needs the cause and the next step, or a retry that actually retries.

## Process

<scope_check>
If the user names ≤2 specific surfaces or screens, skip the Task-tool exploration
phase. Read those files directly and move to the grilling loop.
</scope_check>

### 1. Explore

Read the Kitty grounding above, then walk the user-facing surfaces. Use the Task
tool (`subagent_type=explore`) for broad exploration only when the scope is large.
For each surface the user touches daily, ask:

- **State coverage**: can this surface be loading / empty / error / degraded / stale?
  Does it show the right `AsyncState` for each, or does it show a blank pane, an
  eternal spinner, or nothing at all?
- **Honesty**: when data is unavailable, does it say "couldn't load" or does it
  silently render empty/zero (hiding the gap)?
- **Copy**: does every message tell the user what happened and what to do next? Or
  is it "Error" / a raw exception / a dead end?
- **Feedback**: when the user acts, do they get confirmation, progress, or silence?
  Is perceived latency acknowledged (skeleton / progress / retrying state)?
- **Recovery**: when something fails, can the user retry / reconnect from the
  surface, or must they reload the whole app?
- **Consistency**: does this surface use the canonical `AsyncState` / `StatusBadge`
  vocabulary, or does it roll its own divergent states?

Apply the **daily-touch test** to rank: frequency × cost-per-occurrence. The
highest-leverage friction is on the surfaces hit most often.

### 2. Present candidates

Present a numbered list of UX friction points, ranked by the daily-touch test. For
each candidate:

- **Surface** — which screen/component, named in Kitty vocabulary
- **State** — which of loading / empty / error / degraded / stale is mishandled
- **Current experience** — what the user sees today (blank / spinner / raw error /
  optimistic lie / dead end)
- **Friction cost** — what it costs the user each time, and how often they hit it
- **Smallest fix** — the minimal change (usually: use `AsyncState` with the right
  state + honest copy + a retry)

**Use Kitty domain vocabulary** (from `docs/ARCHITECTURE.md` and the components
themselves) **and the glossary above.** Talk about "the `WorkView` degraded state" —
not "the work page when it's broken."

**Cross-layer handoffs**: if the fix requires the backend to surface a cause it
currently swallows, mark it — that's `harden-codebase` work feeding this skill. If
the fix reveals a structural problem (one component owning too many states), mark it
— that's `improve-codebase-architecture`.

Propose fixes only after the user picks a candidate. Until then, ask: "Which of
these would you like to explore?"

### 3. Grilling loop

Once the user picks a candidate, drop into a grilling conversation. Walk the
experience tree with them — every state the surface can be in, what the user should
see in each, what the copy says, whether a retry is real, what "honest" looks like
when data is partial vs absent, and how the fix proves itself (a test that the
surface renders the right `AsyncState`, mutation-checked per `verify-by-mutation`).

Side effects happen inline as decisions crystallize:

- **Naming a new user-facing state or term?** Add a short definition to
  `docs/ARCHITECTURE.md` or a new `docs/CONTEXT.md` using
  [CONTEXT-FORMAT.md](../improve-codebase-architecture/CONTEXT-FORMAT.md) (shared).
- **Sharpening fuzzy UX copy during the conversation?** Update the relevant
  component right there.
- **User rejects the candidate with a load-bearing reason?** Offer an ADR at
  `docs/adr/NNNN-title.md`, framed as: _"Want me to record this as an ADR so future
  UX reviews don't re-suggest it?"_ See
  [ADR-FORMAT.md](../improve-codebase-architecture/ADR-FORMAT.md) (shared).
- **The fix needs a runtime failure to become visible?** Hand off to
  `harden-codebase` — it owns making the failure loud; this skill owns making the
  loud failure honest and actionable for the user.
