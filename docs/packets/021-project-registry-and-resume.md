# Packet 021 — Project registry + resume (the real P6)

- **Status:** 📋 ready — executor-ready (authored 2026-07-04). Split out of
  016 after discovering 016's premise was wrong (see below). Foundation for
  Wave 3.
- **Best executor:** Claude Code; the `resume()` render format is worth a
  strongest-model pass once real data is flowing, per the original P6 note.
- **Purpose:** Kill resume-archaeology for Jacob's real-world projects, not
  just Kitty's own repo. `docs/OPERATOR_STRATEGY.md` §10 / P6 already
  designed this in detail — this packet is that design, corrected for what
  actually exists on main today, made executor-ready.

## Why this packet exists (read before building anything)

Packet 016 ("next-step navigator") claimed *"Project resume shipped in #71
(`gateway/project_store.py`, `project_resume.py`) — the navigator is a
consumer of `resume()`, not a rewrite."* That's false. #71 shipped
`./kitty resume` / `scripts/resume.py` — a dev-tool that summarizes **the
kitty repo's own state** (branch, open PRs, test counts) for picking up a
coding session. It has zero relationship to tracking Jacob's real-world
projects (car repair, benefits paperwork, job search, kitty-as-a-project).
Two different things share the name "project resume": the registry's
"006 ✅ shipped (#71)" is true for the dev tool only.

The actual foundation — a `projects` table plus a git/memory/todo/signal
composer — was designed in §5.8/§10/P6 of `OPERATOR_STRATEGY.md` but never
built as its own packet. This packet is that build. 016 depends on it and
must not be started until this ships.

## Decisions already made (do not reopen — from OPERATOR_STRATEGY §10/P6)

- `projects` table, not a new store type: `id, name, kind, paths_json,
  status, last_touched, summary, open_questions_json, next_actions_json,
  delegable_json, links_json`. `kind` is `code | admin | creative` — non-code
  projects (benefits, job search) are the same table with document/journal
  signals instead of git. That's the test that the model isn't secretly a
  dev tool.
- `refresh(id)` composes from: local git (`git log` / branch state for
  registered paths — no GitHub connector dependency; 020 enriches this
  later, is not required now), `memory_graph.search_all(query)` for
  journal/chat mentions, signals referencing the project. **Todos are not
  composed in v1** — `todo_store` has no project-tagging field today, and
  adding one is its own small migration; note it as a follow-on, don't
  smuggle a schema change into this packet's "files likely touched."
- `resume(id)` renders the packet: status line, what changed since
  `last_touched`, open questions, next 3 actions, delegable items.
- The kitty repo is project #1 — seed it. Dogfoods the loop instantly since
  all its data sources (git, this repo's own journal/signals) are already
  local.
- Routes: `GET /projects`, `POST /projects`, `POST /projects/{id}/refresh`,
  `GET /projects/{id}/resume` — same sync-handler pattern as
  `gateway/routes/state.py` (git subprocess calls block; run in FastAPI's
  worker pool, not the event loop).
- UI: out of scope for this packet. HomeState already has five panels
  (`What changed` / `Needs you` / `Open loops` / `Today` / `Capture`) per
  #98/#100 — a project-cards panel is a small P4-style extension for
  whoever builds 016's UI half, not this one.

## Exact scope

1. **Migration `gateway/migrations/010_projects.sql`** (009 is taken —
   `009_actions.sql` shipped in #65/#67). Table shape per "Decisions" above.
   Index on `status` and `kind` (mirrors `idx_actions_status`).
2. **New `gateway/project_store.py`** — CRUD, following the `gateway/db.py`
   / per-store-module pattern (see `action_queue.py`, `todo_store.py` for
   house style): `create(name, kind, paths=None, links=None) -> dict`,
   `get(id) -> dict | None`, `list_projects(status=None) -> list[dict]`,
   `update_fields(id, **fields) -> dict`, `touch(id)` (bumps
   `last_touched`).
3. **New `gateway/project_resume.py`**:
   - `refresh(id) -> dict`: for `kind="code"` with `paths_json` set, run
     `git log`/`git branch`/`git status` per path (subprocess, bounded
     timeout — mirror `state_composer.SOURCE_TIMEOUT_SECONDS`), plus
     `memory_graph.search_all(project.name)` for journal/chat mentions,
     plus `signal_store` rows whose payload references the project (match
     on project name in payload text — exact scheme is an implementation
     call, not a spec requirement). Writes `summary`, `open_questions`,
     `next_actions`, `last_touched` back via `project_store.update_fields`.
     A source that fails (bad path, no git repo) produces
     `{"ok": False, "error": ...}` for that source only — same
     no-single-source-failure-kills-the-read pattern as
     `state_composer.compose_now`.
   - `resume(id) -> dict`: renders the stored fields into the packet shape
     from "Decisions." Pure read — no composition, no side effects.
4. **Routes** `gateway/routes/projects.py`, registered in
   `gateway/routes/register.py` alongside `state`/`actions`/`inbox`.
5. **Seed:** on first migration or via a one-time script, register the
   kitty repo itself as project #1 (`kind="code"`, `paths_json=["."]`
   resolved to the repo root).

## Files likely touched

- New: `gateway/migrations/010_projects.sql`, `gateway/project_store.py`,
  `gateway/project_resume.py`, `gateway/routes/projects.py`,
  `tests/test_project_store.py`, `tests/test_project_resume.py` (with a
  fixture git repo — `tmp_path` + `git init` + a couple commits, not a
  mock), `tests/test_projects_routes.py`.
- Edits: `gateway/routes/register.py` (register the new router).

## Files not to touch

- `memory_graph` internals — consume `search_all()`, don't reach into its
  adapters.
- `chats_store` / `journal_store` schemas.
- `todo_store` schema — no project-tagging column in this packet (see
  "Decisions"); note it as a follow-on if Jacob wants todos composed later.
- `HomeState.tsx` / any frontend — this is the data layer only. 016 (or a
  small P4-style follow-on) owns the UI card.
- `gateway/routes/state.py` — `state_composer` stays the read-everything
  composer; projects gets its own routes, not a new `/state/now` section
  (open loops already surfaces `inbox`/`actions`/`needs_jacob` counts per
  #100 — don't duplicate that here).

## Steps

1. Migration + `project_store.py` CRUD → unit tests.
2. `refresh()` git composer against a fixture repo (real `git init` +
   commits in `tmp_path`, not mocked subprocess) → test idempotency (two
   refreshes with no repo changes produce the same `last_touched`-adjacent
   fields, modulo timestamps).
3. `memory_graph.search_all` + signal-matching composition → tests with a
   stubbed graph result and stubbed signal rows.
4. `resume()` renderer → tests against a hand-built project row.
5. Routes + registration → integration test hitting all four endpoints.
6. Seed the kitty repo as project #1.

## Acceptance

- `refresh(1)` (kitty repo) returns real branch/PR-adjacent git state
  (branch name, dirty flag, recent log) and picks up genuine journal/chat
  mentions if any exist — no fabricated fields.
- `refresh` is idempotent: calling it twice with no underlying change
  doesn't drift `summary`/`open_questions`/`next_actions`.
- A manually registered non-code project (`kind="admin"`, no `paths_json`)
  renders via `resume()` with zero git data and no error — proves the model
  isn't secretly a dev tool.
- A source failure (bad git path) surfaces as a per-source error, not a
  500 or a silently empty resume.
- Full suite green: `python3.12 -m pytest tests/ -q --tb=short`.

## Verification commands

```bash
python3.12 -m pytest tests/test_project_store.py tests/test_project_resume.py tests/test_projects_routes.py -q --tb=short
curl -H "Authorization: Bearer $GATEWAY_SECRET" http://127.0.0.1:8000/projects/1/resume | python3.12 -m json.tool
```

## Risks

- **Summary drift if LLM-refreshed later:** this packet's `refresh()` is
  mechanical (git + raw memory/signal hits), no LLM summarization yet — if
  a future packet adds LLM-written summaries, keep `summary` last-written-
  wins with model + timestamp recorded, per the original P6 note.
- **Git ops on missing/moved paths:** explicit per-source error, never a
  silent empty result (same discipline as `state_composer`).
- **Scope pressure to also build the todo-tagging column and the UI
  card:** don't. Both are named follow-ons, not this packet.

## Rollback

Revert the PR. New table, inert until seeded; nothing else depends on it
yet (016 is blocked on this, not the other way around).

## Unlocks

016 (next-step navigator) — the actual consumer. 016's own scope sketch
(next_step.py, delegable flag feeding 007) is otherwise unchanged; only its
"what already exists" section was wrong and needs correcting once this
ships (see that packet's note).

## Too broad if

- It builds the UI project-card, LLM-based summarization, todo-project
  tagging, or GitHub-enriched composition (020's job later). Data layer
  only: table, composer, routes, kitty-repo seed.

## Jacob reviews

- `resume(1)` (kitty project) — does the composed state actually match
  reality (branch, recent commits, any journal mentions)?
- Whether a manually-registered non-code project is worth seeding now
  (benefits/job-search) or waiting for 017/019 to register their own.
