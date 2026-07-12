# North Star — written 2026-07-11, meant to outlive every model that reads it

This file exists because the expensive reasoning model is leaving and the
project must not depend on it. Three audiences, one truth. If any future doc
contradicts this one on *purpose*, this one wins until Jacob says otherwise.

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
The `life-first-v1` initiative in the Builder queue implements this.

## 3. The economics — Kitty does not need an expensive model

Verified against the live config (`gateway/litellm_config.yaml`, 2026-07-11):

- `kitty-default` → DeepSeek v4 flash via OpenRouter — fractions of a cent
- `kitty-default-or` → `gemini-2.0-flash-exp:free` — literally $0
- `kitty-default-gemini`, `kitty-agentrouter`, `kitty-openai` — cheap tiers

Daily companion use (chat, briefs, next steps, capture) runs on these today.
The expensive models were only ever used to *design* the system — and the
design is done and written down. What remains is bounded implementation, and
the whole KittyBuilder pipeline (queue → isolated worktree → free worker →
independent review → operator publish) was built precisely so cheap and free
models can do that safely. The factory is the inheritance.

**For Jacob, in plain words:** you are not locked out. Open Kitty every day
and use it — chat, capture, ask "what's next". It runs on the free/cheap
routes already configured. When you want it improved, you don't need to hire
an expensive model to think; the thinking is in `docs/BLUEPRINT.md` and the
Builder queue. Any capable free agent pointed at this repo can pick up a
packet and the system will catch its mistakes (that's what the trust lane
was for).

## 4. Operating manual for whoever reads this next (probably a cheaper model)

You don't need to be brilliant. You need to be honest and bounded. The
system is designed to make that enough:

1. Read `.claude/HANDOFF.md`, `.claude/STATE.md`, `docs/BLUEPRINT.md`. Don't re-audit.
2. Work from the Builder queue: `./kitty builder initiative list`, then
   `status <id>`. Take ONE packet. Stay inside its allowed paths.
3. Failures stay failures. Never return `[]`/`null`/`completed` to hide an
   error. The verifier's exit code is authoritative. If you can't finish,
   write what you tried into the handoff and stop — that's a success.
4. UI work isn't done until it's seen working in a browser. No exceptions.
5. Never touch: `.env`, `data/` personal stores, push/merge, security/auth
   (T2 → Jacob decides, with whatever review he can get).
6. Small diffs. One packet per session. Update `.claude/STATE.md` before stopping.
7. When you're unsure whether something helps Jacob's life or just polishes
   the machine — it's the machine. Pick the other thing.

## 5. What "done" looks like

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

That's the whole dream, and every piece of it already has rails in this
repo. Keep laying track.
