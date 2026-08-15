# North Star — written 2026-07-11, meant to outlive every model that reads it

This file owns product purpose. It exists so Kitty does not depend on any one
model, vendor, or session. The authority and supersession rules in
`docs/AUTHORITY_MAP.md` decide other conflicts; this file does not own current
implementation or queue state.

---

## 1. What Kitty is for (the part everyone keeps forgetting)

Kitty is not a coding project. Kitty is how Jacob gets help that money
usually gates: structure, memory, follow-through, and a patient second brain
that shows up every single day and never bills him.

Look at the actual projects in Kitty's own database: **Job search. Benefits.
Furthering education.** That is the product roadmap. Everything in
`docs/BLUEPRINT.md` — the resume loop, honest state, delegation — was
scaffolding for *this*:

> Every morning, Kitty knows where Jacob's life stands and hands him one
> concrete, doable next move. Not ten. One. With the why. And it remembers
> what happened to yesterday's move.

A session that improves KittyBuilder but doesn't move Jacob's actual life
forward is overhead. Sometimes necessary, never the point. The measure of
success is mornings Jacob *wants* to open Kitty — nothing else.

## 2. Life-first ordering (decision, see ADR 0016)

When Kitty generates "What's Next", life projects (job search, benefits,
education, health, money) outrank code projects — including Kitty itself.
Kitty must never become a hobby that eats the time it was built to free.
Life-first selection is shipped in the product. Never infer current Builder
queue contents from this decision; inspect the supported Builder projection.

## 3. The economics — Kitty does not need an expensive model

Model names and prices drift, so live routing facts must be verified before
use. The durable economic target is roughly 90–95% of the available quality at
materially lower cost. KittyBuilder starts with the cheapest worker that meets
the packet's capability and risk needs and escalates only when evidence
justifies it. Architecture is never assumed complete merely because it is
written down.

**For Jacob, in plain words:** you are not locked out. Open Kitty every day
and use it — chat, capture, ask "what's next". Kitty should route work
cost-consciously, make uncertainty visible, and explain important decisions so
Jacob gains skill rather than dependence. Models are replaceable workers;
verified repository and Builder evidence outlive them.

## 4. Kitty is the principal agent

Jacob talks to Kitty. Kitty is the thinking partner, intent compiler, product
lead, and project manager. It retrieves only relevant context, says what is
missing, challenges assumptions, plans evidence, and proposes a precise Mission.
KittyBuilder then organizes authorized execution. Proactivity is relevance-
gated, permissions for access/retrieval/monitoring/memory/action stay separate,
and material results include concise teach-back.

## 5. Operating manual for whoever reads this next

You don't need to be brilliant. You need to be honest and bounded. The
system is designed to make that enough:

1. Execute `START_HERE.md`, generate `./kitty context --agent`, and reject stale
   inherited context before acting.
2. Read the approved Mission. If Builder execution is relevant, inspect its
   supported state and take only an eligible, authorized packet.
3. Failures stay failures. Never return `[]`/`null`/`completed` to hide an
   error. The verifier's exit code is authoritative. If you can't finish,
   write what you tried into the handoff and stop — that's a success.
4. UI work isn't done until it's seen working in a browser. No exceptions.
5. Never touch: `.env`, `data/` personal stores, push/merge, security/auth
   (T2 → Jacob decides, with whatever review he can get).
6. Small diffs. One packet per session. Replace the current checkpoint before
   stopping.
7. When you're unsure whether something helps Jacob's life or just polishes
   the machine — it's the machine. Pick the other thing.

## 6. What "done" looks like

Not a finished app. A morning ritual that holds:

- Jacob opens Kitty (phone or Mac). It says what happened, what's next, what
  needs him — truthfully, in his own projects' terms.
- The next move is small enough to actually do, and doing it compounds:
  applications sent, benefits claimed, courses started, captures resurfaced
  at the right moment.
- When something breaks, Kitty says so plainly and it's fixable by a free
  worker with a bounded packet.
- Nobody involved — Jacob or any model — has to pretend something works
  when it doesn't.

That's the dream. Some rails are shipped, some are active work, and some remain
unknown until verified. Keep laying track without pretending the destination is
already complete.
