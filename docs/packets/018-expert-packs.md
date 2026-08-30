# Packet 018 — Expert packs: car, body, and proactive headlines

- **Status:** 🧭 planned — gated on 008-remainder (collections + expert
  retrieval modes) shipping first. This packet is the payoff Jacob named
  2026-07-04: *"the automotive expert will be like — yo, your fuel trim on
  bank one was a little high, let's figure that out… have you dealt with
  the rust yet, here are some strategies for your suspension, here are
  some cheap parts, knock this off in a weekend."*
- **Best executor:** Claude Code / Codex for plumbing; each expert's
  specialist prompt is strongest-model work.
- **Purpose:** Turn 008's expert-retrieval machinery into named experts
  that (a) answer from Jacob's uploaded documents with citations and
  (b) **speak first** — emitting suggestion signals that show up as
  headlines in the brief, not waiting to be asked.

## Packs in scope (v1: two, in this order)

1. **Automotive** — service manuals, OBD/scan readings, repair notes,
   parts research. Proactive: reads new car-related captures (a photo of a
   scan tool, a note about a noise) and emits weekend-sized suggestions
   with rough parts cost. Cloud-ok content class unless Jacob marks
   otherwise.
2. **Body/health** — posture, stretches, sauna/steam routines, back and
   nervous-system material Jacob uploads. Photos for posture checks and
   anything health-adjacent are `health_admin`-class: local-only under
   D10, no exceptions. Proactive: gentle, low-frequency ("here's one
   stretch for the thing you mentioned"), never diagnostic, never medical
   advice beyond his own uploaded sources.

The **disability/benefits expert** rides packet 017's collections and is
specified there. The **recovery pack** (recovery books, Dharma/12-step,
relapse-prevention notes — already named in 008's examples) is **parked:
built only on Jacob's explicit yes, entirely local-only.** Standing offer,
zero nagging.

## Scope sketch (for the authoring pass)

- Per-pack config: specialist prompt, allowed collections, privacy class,
  citation rules (008 item 5's contract), and a *proactive policy* — what
  new signals/captures the expert watches and how often it may speak.
- Expert suggestions are signal rows (`source="expert.automotive"`, dedupe
  keys) → brief headlines → optionally proposed T0/T1 actions ("add
  'order control-arm bushings' to todos?").
- Rate limit per pack (e.g. max one unsolicited headline/day) — experts
  that spam get ignored, and ignored experts are dead features.

## Dependencies

- 008-remainder (collections, expert modes, expert-path privacy wiring) —
  hard dependency. 015 for delivery, 017's ingestion rails for documents.

## Acceptance sketch

- Uploading a fixture service-manual chunk + a fixture scan note produces
  a cited answer AND an unsolicited, correctly-rate-limited headline.
- A body-pack query with cloud routing attempted raises the D10 boundary.
- An expert with no relevant sources says so instead of improvising (008
  item 5 contract holds).

## Jacob reviews

- Each pack's first three headlines: useful, or noise? His call kills or
  keeps the proactive policy per pack.
- The recovery pack's existence: one explicit yes/no, asked once, by him
  bringing it up — not by Kitty.

## Too broad if

- More than two packs in one PR, autonomous purchases/bookings from
  suggestions, or any health content leaving the machine.
