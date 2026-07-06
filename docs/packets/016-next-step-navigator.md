# Packet 016 — Next-step navigator ("just tell me what B is")

- **Status:** 📋 ready — executor-ready (authored 2026-07-05, unblocked by
  021 shipping in #106).
- **Best executor:** Claude Code for the plumbing; the next-step prompt
  itself is strongest-model work, reviewed against real projects — see
  "Jacob reviews." This is the first packet in the queue whose output is
  LLM-generated content Jacob has to judge, not just mechanical
  composition — build it, but don't consider it "done" until he's read a
  week of real Bs.
- **Purpose:** Jacob's own words (2026-07-04): *"I want to go from A to Z,
  but I just need to know what B is."* For every active project, Kitty
  maintains exactly one concrete, doable next step — visible in the brief,
  pushed when it changes, answerable on demand. Not a dashboard of
  everything: one clear B, plus a one-sentence line about what's already
  done (SOUL: honest, never flattering).

## Correction (2026-07-04, kept for history)

This packet originally claimed project resume shipped in #71. That was
wrong — #71 shipped `./kitty resume`, a dev-tool for the kitty repo's own
state, unrelated to tracking Jacob's real-world projects. The real
foundation shipped as **021** (#106): `gateway/project_store.py` +
`gateway/project_resume.py`, `refresh(id)`/`resume(id)`. This packet is
now unblocked and is exactly the consumer originally intended.

## What already exists (do not rebuild)

- **021 (#106)** — `project_store.get/list_projects/update_fields`,
  `project_resume.refresh(id)`/`resume(id)`. `resume()` already returns
  `next_actions` (up to 3, mechanical, no LLM) — this packet does NOT
  reuse that field for "B." "B" is a narrower, LLM-curated singular concept
  (see "Exact scope" — why a new table, not an overload of `next_actions`).
- **003** — action queue. **007** — `packet.delegate` (T1, already in
  `config/action_tiers.json`). A step marked delegable does not
  auto-propose an action in this packet (see "Too broad if") — the flag is
  informational until Jacob acts on it.
- **012 (D10/§17.3)** — the privacy boundary is already enforced in
  `gateway.llm_client.call_llm(..., privacy_tier=, content_class=)`
  (`PRIVACY_LOCAL_ONLY = {"journal", "mail_body", "health_admin"}`). This
  packet is a caller, not a rewrite: `kind="code"` projects call with
  `privacy_tier="cloud_ok"`; `kind="admin"`/`"creative"` call with
  `privacy_tier="local"` (the safe default) and a `content_class` matching
  what the project actually holds (e.g. `"health_admin"` for a benefits
  project) so `enforce_privacy_boundary` can do its job.
- **015 (#103)** — `gateway.push.push_to_jacob(...)` for delivery.
  **021's `resume()`** is what "why is B next" gets built from.

## Decisions needed before building (resolve here, not mid-flight)

1. **"B" is its own table, not a `projects` column.** `next_actions_json`
   (021) is the mechanical top-3 from git/memory/signals — general state.
   "B" is a single LLM-curated pick with its own lifecycle (generated_at,
   delegable, invalidation on a completed action). Overloading
   `next_actions_json` would conflate the two and make 021's "no LLM in
   v1" guarantee false by proxy. New table: `project_next_steps`.
2. **Recompute trigger: on `refresh()`, not on a separate schedule.**
   `next_step.generate(id)` is called right after
   `project_resume.refresh(id)` (same route, same manual trigger) — no new
   cron job. Keeps "recompute on project refresh" literal, per the scope
   sketch, and avoids a second scheduler to reason about.
3. **Push-on-change, not push-on-every-refresh.** Compare the newly
   generated step text to the stored one; call `push_to_jacob` only when
   it differs (or was previously null). Refreshing a project that hasn't
   moved must not spam a push — this is the "notification spam kills the
   channel" risk 015 already flagged.

## Exact scope

1. **Migration `gateway/migrations/011_project_next_steps.sql`**:
   `project_next_steps(project_id INTEGER PRIMARY KEY REFERENCES
   projects(id), step TEXT NOT NULL, why TEXT NOT NULL, recent_win TEXT,
   delegable INTEGER NOT NULL DEFAULT 0, generated_at REAL NOT NULL)`.
   One row per project — a new `generate()` call replaces it, it does not
   accumulate history.
2. **New `gateway/next_step.py`**:
   - `generate(project_id) -> dict`: calls `project_resume.resume(project_id)`
     (the just-refreshed state — caller's job to `refresh()` first, this
     function does not refresh), builds one `call_llm` prompt asking for
     exactly one step + one-sentence "why it's next" + one-sentence
     "what's already done" (the feel-good line — required, not decoration)
     + a delegable y/n, with `response_format={"type": "json_object"}` so
     the reply parses directly. Privacy tier/content_class chosen from
     `project["kind"]` per "Decisions" above. Writes the row via
     `INSERT OR REPLACE`. Returns `{step, why, recent_win, delegable,
     generated_at, changed: bool}` — `changed` is the push-trigger signal
     from Decision 3.
   - `get(project_id) -> dict | None`: pure read of the stored row.
3. **Wire into the refresh route**: `gateway/routes/projects.py`'s
   `post_refresh` calls `project_resume.refresh(id)` then
   `next_step.generate(id)`, and if `changed` is true, pushes via
   `gateway.push.push_to_jacob(f"{project['name']}: {step}", kind="info",
   title="What's next", dedupe_key=f"next-step-{project_id}-{step_hash}")`.
   Response body gains a `next_step` key alongside the existing refresh
   shape.
4. **Route** `GET /projects/{id}/next` — pure read via `next_step.get`;
   404 if no step has ever been generated (never refreshed with this
   packet live) — do not fabricate a placeholder step.
5. **Brief integration**: `gateway/brief.py`'s `generate_brief()` gains a
   `next_steps: list[dict]` field — one entry per active project with a
   generated step, ordered by staleness (`last_touched` ascending) then
   project `id`. `gateway/brief_scheduler.py`'s `_format_brief_text` grows
   a "What's B" bullet block (cap at 3 projects — brief is a 5-bullet
   digest, not a project dump; SOUL's anti-nag rule applies to the brief
   too, not just the per-project view).
6. **Completed-action invalidation**: when `action_queue.approve`/
   `execute` resolves an action whose `source_kind`/`source_id` points at
   a `project_next_steps` row (source tagging is this packet's job — tag
   `source_kind="next_step"`, `source_id=str(project_id)` on any action a
   delegable step's UI button proposes, *outside* this packet's own code
   path since it doesn't auto-propose — this is forward-compatible
   plumbing for whichever surface adds the button), delete that project's
   `project_next_steps` row so the next `resume`/`refresh` regenerates
   instead of showing a stale, already-done "B."

## Files likely touched

- New: `gateway/migrations/011_project_next_steps.sql`,
  `gateway/next_step.py`, `tests/test_next_step.py`.
- Edits: `gateway/routes/projects.py` (wire generate + push into refresh,
  add the `/next` route), `gateway/brief.py` (`next_steps` field),
  `gateway/brief_scheduler.py` (`_format_brief_text` "What's B" block),
  `tests/test_project_resume.py`-adjacent route tests, `tests/test_brief*`.

## Files not to touch

- `gateway/project_store.py` / `gateway/project_resume.py` schemas —
  021's `next_actions_json` stays mechanical; don't repurpose it (see
  "Decisions").
- `gateway/llm_client.py` internals — call `call_llm()`, don't add a new
  provider path or change `enforce_privacy_boundary`.
- `config/action_tiers.json` — no new action kind. Delegable is a flag,
  not an auto-proposal (see "Too broad if").
- `HomeState.tsx` / any frontend — data + brief layer only. A "What's B"
  home-console card is a follow-on for whoever next touches HomeState.

## Steps

1. Migration + `next_step.py` `generate()`/`get()` → unit tests with a
   stubbed `call_llm` (no real network/model calls in the suite — mirror
   how `test_project_resume.py` stubs `_run_memory_search`).
2. Wire into `post_refresh` + the `changed` → push-dedupe logic → route
   tests asserting push fires once on change, not on a no-op refresh.
3. `GET /projects/{id}/next` route + 404-when-never-generated test.
4. Brief integration → test that `generate_brief()`'s `next_steps` is
   capped and ordered correctly; `_format_brief_text` renders it.
5. Completed-action invalidation → test that resolving a tagged action
   clears the stored step.

## Acceptance

- The kitty repo project (already seeded, already has real git/memory/
  signal state from 021) produces one concrete, non-fabricated step whose
  "why" plausibly follows from its actual `resume()` state — Jacob judges
  this qualitatively (see "Jacob reviews"), but mechanically: it must not
  be empty, generic filler, or the same static string every refresh with
  no underlying change.
- A registered non-code project (benefits, once 017 registers one; a
  manually-created `admin` project is enough to test this packet in
  isolation) gets a step generated with `privacy_tier="local"` — assert
  this via the stubbed `call_llm`'s captured kwargs, not by trusting the
  code path.
- Refreshing twice with no underlying project change does not re-push
  (dedupe holds); refreshing after a real change (new commits, e.g.) does.
- Resolving the tagged action behind a delegable step clears it; the next
  refresh generates a new one.
- Full suite green: `python3.12 -m pytest tests/ -q --tb=short`.

## Verification commands

```bash
python3.12 -m pytest tests/test_next_step.py tests/test_projects_routes.py tests/test_brief_scheduler.py -q --tb=short
curl -H "Authorization: Bearer $GATEWAY_SECRET" -X POST http://127.0.0.1:8000/projects/1/refresh | python3.12 -m json.tool
curl -H "Authorization: Bearer $GATEWAY_SECRET" http://127.0.0.1:8000/projects/1/next | python3.12 -m json.tool
```

## Risks

- **Bad Bs erode trust faster than no B at all.** This is why "Jacob
  reviews" names a full week, not a single spot-check — a collaborator
  feature that nags or misreads state is worse than the dashboard-of-
  everything it's replacing. If the first week's Bs are weak, the fix is
  prompt iteration, not shipping faster.
- **Notification spam kills the channel** (015's own risk, inherited
  here) — Decision 3's push-on-change-only guard is load-bearing, not
  optional polish.
- **Privacy misroute.** A benefits/admin project's content reaching a
  cloud model would be a real D10 violation, not a style nit — the
  `content_class` tagging in "Decisions" #… (see "What already exists")
  must actually be exercised in tests, not just asserted by reading the
  code.

## Rollback

Revert the PR. New table + new module; `project_store`/`project_resume`
untouched, so 021 keeps working standalone. Brief falls back to its
pre-016 shape (`next_steps` key simply absent).

## Unlocks

The "one concrete next step" line in the move-in-day bar
(`docs/packets/README.md` §"The finish line") — this is the second of
five move-in criteria, after the phone channel (015, done) and before the
safety net (017).

## Too broad if

- It auto-proposes or auto-executes a `packet.delegate`/any action from a
  delegable step. It builds a "What's B" UI card (HomeState is out of
  scope here — brief + API only). It adds a second recompute schedule
  beyond "on refresh." It generates more than one step per project, ever.

## Jacob reviews

- The first week of generated Bs, per project: are they actually the
  right next steps, and do they feel like a collaborator or a nag? One
  thumbs-up/down per B is the whole review loop — no formal UI for this
  in v1, just tell Kitty (chat) and note the pattern in
  `docs/LEARNINGS.md` if the prompt needs work.
- Whether the "What's B" brief block competes for space with headlines/
  intention in a way that makes the brief worse, not better.
