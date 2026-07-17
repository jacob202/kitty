# Project Status

**Verified:** 2026-07-17 against `origin/main` at
`167fa24accb0ff1b574a0a833786a6cdf22957d8`
**Canonical repo:** `/Users/jacobbrizinski/Projects/kitty`

Branch, worktree, dirty state, and relation to `origin/main` are derived by
`./kitty context --agent`; they are not copied into this status document.

## What's Shipped

| Phase                   | Description                                                  | Status               |
| ----------------------- | ------------------------------------------------------------ | -------------------- |
| Phase B (B0–B5)         | Storage consolidation, SQLite seam, storage router           | ✓ Shipped            |
| Phase C chats (C0–C6)   | Chat sessions migrated to SQLite                             | ✓ Shipped            |
| Phase C journal (B0–B6) | Journal migrated to SQLite                                   | ✓ Shipped            |
| Phase E                 | PWA seam (manifest, service worker, install banner)          | ✓ Shipped            |
| Memory loop             | Session stop hook + recall-thread readback + /remember skill | ✓ Shipped (#48)      |
| Mypy gate               | 80 gateway mypy errors cleared; typecheck now blocks CI      | ✓ Shipped (#51)      |
| Session persistence     | Chat sessions survive restart; SOUL reads real config        | ✓ Shipped (#765caa3) |
| Startup preflight       | Reliable preflight runs on `./kitty up`                      | ✓ Shipped (#50)      |
| Phase 3–5 product       | Chat, brief, memory, settings polish; merged to main         | ✓ Shipped (#14f5865) |
| Gateway deepening       | Route consolidation, fail-loud, duplicate route contracts     | ✓ Shipped (#569608b) |
| Builder improvements    | Queue, run-loop safety rails, initiative doctor preflight     | ✓ Shipped            |
| Builder investigation UI | Bounded status projection and read-only Home/Builder surface  | ✓ Shipped (#183)     |
| Fail-loud sweep         | Verifier false-green, enrichment markers, model discovery     | ✓ Shipped (Card C)   |

## Live release and Builder state

GitHub reported no open pull requests at the 2026-07-17 audit. PR #181 shipped
the Engineering Leverage and Builder identity work, #183 shipped the Builder
status/UI surface, and #184 repaired the production browser-smoke build gate.

The supported Builder projection reported zero initiatives and one cancelled
task, with no queued, claimed, running, blocked, review, or failed work. Builder
doctor reported 13 pass, 1 warning, 0 failures; the warning is that the
KittyBuilder worktree root has not yet been created. This is an observation,
not a substitute for a fresh Builder probe.

## Last verified test state

- Builder UI release: 616 backend tests, 150 frontend tests, TypeScript, Ruff,
  mypy, browser QA, and production Webpack compilation passed before #183/#184
  merged.
- The Project Control Plane mission owns its current validation ledger in
  `.claude/STATE.md`; do not promote an old count into a current claim.
- `./kitty doctor --json` on 2026-07-17 still reported host prerequisites that
  need attention: missing root `.env`, missing root `venv`, and unavailable
  mem0. Gateway and LiteLLM service probes passed. These failures are explicit
  and are not being reclassified as code success.

## Runtime Shape

- Gateway: FastAPI on `127.0.0.1:8000`
- LiteLLM proxy: `127.0.0.1:8001`
- Data: `data/kitty/kitty.db` (SQLite), `data/chromadb/` (vectors), `data/inbox.jsonl` (capture)
- Start: `./kitty up` | Stop: `./kitty down` | Health: `./kitty doctor --json`

## Active Technical Debt

- Mission runtime and autonomous Kitty→Builder submission are not implemented;
  ADR 0017 is a contract only.
- Safe bounded Builder log and artifact delivery remains unavailable by design.
- Root doctor prerequisites listed above remain unresolved and must stay loud.

## What's Next

The one approved mission is `docs/ACTIVE_MISSION.md`: establish the Project
Control Plane / Continuity Foundation. The exact current action and blockers
live only in `.claude/STATE.md` and must match its context receipt.

After this mission, the next product step is to implement the versioned Mission
runtime and governed submission bridge in a separately approved packet. Do not
enable autonomous Builder mutation as part of the foundation.

Authority routing lives only in `docs/AUTHORITY_MAP.md`.
