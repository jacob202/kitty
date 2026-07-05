# Packet 016 — Next-step navigator ("just tell me what B is")

- **Status:** 🧭 planned — needs an executor-ready authoring pass.
  **Blocked on 021** (see correction below); do not author or build until
  021 ships.
- **Best executor:** Claude Code; the next-step prompt itself is
  strongest-model work, reviewed against real projects.
- **Purpose:** Jacob's own words (2026-07-04): *"I want to go from A to Z,
  but I just need to know what B is."* For every active project, Kitty
  maintains exactly one concrete, doable next step — visible in the brief,
  pushed when it changes, answerable on demand. This is the collaborator
  feature: not a dashboard of everything, one clear B, plus a line of
  encouragement about what's already done (SOUL: honest, never flattering).

## Correction (2026-07-04) — the line below was wrong

This packet originally claimed *"Project resume shipped in #71
(`gateway/project_store.py`, `project_resume.py`)."* That's false: #71
shipped `./kitty resume` / `scripts/resume.py`, a dev-tool that summarizes
**the kitty repo's own state** (branch, PRs, tests) for picking up a coding
session — nothing to do with tracking Jacob's real-world projects. The
actual foundation (a `projects` table + git/memory/signal composer,
designed in `OPERATOR_STRATEGY.md` §10/P6) was never built. It's now its
own packet: **021 — Project registry + resume**. This packet is a consumer
of 021's `refresh()`/`resume()`, same as originally intended — the target
just didn't exist yet.

## What already exists (do not rebuild)

- **021 (once shipped)** — `gateway/project_store.py` /
  `gateway/project_resume.py`: `refresh(id)`/`resume(id)` composition from
  git, memory, signals (todos not yet composed — see 021's own notes).
  The navigator is a consumer of `resume()`, not a rewrite.
- Action queue (003) — a next step that's actionable can be proposed as a
  T0/T1 action directly.
- Brief scheduler + phone channel (015) for delivery.

## Scope sketch (for the authoring pass)

- `gateway/next_step.py`: for each active project, take the resume packet
  and select or generate ONE next step — small enough for a single session,
  concrete enough to start in five minutes. LLM-assisted; project material
  respects D10 privacy classes (kitty repo = cloud-ok; benefits project =
  local-only).
- Each next step carries: the step, why it's next (one sentence), what got
  done recently (one sentence — the feel-good line is a spec requirement,
  not decoration), and "delegable? y/n" (feeds packet 007).
- `GET /projects/{id}/next` + a "What's B" section in the brief, ordered by
  staleness/stakes. Push via 015 only when a step changes or unblocks.
- Recompute on project refresh; a completed action invalidates the step.
- Anti-nag rule: one B per project. Never a list. Lists are what he has.

## Dependencies

- **021 (blocking — not yet built)** for `refresh()`/`resume()`. 015
  (shipped, PR #103) for delivery. 020 (GitHub connector) later enriches
  code projects with PR/CI state but is not required. 006's `./kitty
  resume` is unrelated — do not confuse the two (see correction above).

## Acceptance sketch

- The kitty repo project returns a real, correct, currently-true next step
  that matches the packet registry's execution order.
- A registered non-code project (benefits, packet 017) returns a next step
  with zero git data.
- Completing the step's action and refreshing yields a *different* step.

## Jacob reviews

- The first week of generated Bs: are they actually the right next steps,
  and do they feel like a collaborator or a nag? One thumbs-up/down per B
  is the whole review loop.

## Too broad if

- It starts executing steps autonomously, generating multi-step plans, or
  building a new planning UI. One B, per project, delivered where he
  already looks.
