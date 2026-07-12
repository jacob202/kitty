# 022 — Magic Kitty: cross-project insight synthesis

**Status:** 🚧 in progress — executor building (orchestrator subagent, free model)
**Activation:** `active_packet`
**Best executor:** strongest-model prompt + Claude Code (free-model calls only)
**Intent:** Kitty reads every active project's `resume()` state at once and surfaces the non-obvious connections between them — the "huh, these are actually related" moment.

## Intake classification

- **Class:** `active_packet` (was `🧭 planned — named, not authored`)
- **Why this is not just an idea:** the route, module, and tests already exist
  on `main` (`gateway/routes/magic.py`, `gateway/magic_kitty.py`,
  `tests/test_magic_kitty.py`) — they shipped inside a broad commit
  (`cdd3367`) before the packet was authored. The missing piece is the
  executor-ready packet contract itself; this file closes that gate and pins
  the acceptance criteria the existing code must satisfy.
- **Why now:** Wave 5 depth work (README execution order). 016 (next-step
  navigator) and 021 (project registry + resume) are shipped, so the inputs
  `magic_kitty` consumes (`project_store.list_projects` + `project_resume.resume`)
  are real and populated by Jacob. Comes after 016, not inside it.
- **Activation trigger:** n/a — already active.

## Demo contract

After this lands, Jacob can see or do this concrete thing:

- [x] `GET /magic` returns a JSON array of cross-project connection insights
      (`kind`, `title`, `detail`, `source`, `confidence`) synthesized across
      all active projects.
- [x] `GET /magic?force=true` bypasses the 5-minute cache and regenerates
      from live project state.
- [ ] visible proof: with ≥2 real projects registered and refreshed, the
      morning brief / home console shows a "Magic Kitty" card. (UI card is a
      follow-on; the API is the human-visible finish line for this packet.)

This is the human-visible finish line. Tests are not enough by themselves.

## Why this exists

Jacob's projects are islands in the UI: each shows its own `resume()` and its
own "B," but nothing connects them. Real life overlaps — a deadline in
`benefits-admin` may hinge on a branch landing in `kitty`; a creative project
may reuse a pattern from a code project. A collaborator should notice that and
say so. `magic_kitty` is the one place that looks across the whole registry at
once.

## Product principle

> Capture comes back at the right moment, without asking Jacob to go hunting —
> and sometimes the right moment is "these two things you're working on are the
> same problem."

## Scope budget

- **Expected diff size:** small (packet file + focused privacy hardening on the
  existing `call_llm` call; implementation is already present on `main`).
- **Expected files touched:** `docs/packets/022-magic-kitty.md`,
  `gateway/magic_kitty.py` (privacy arg), `tests/test_magic_kitty.py` (assert
  captured privacy kwargs), `docs/packets/README.md` (registry row bump).
- **Stop and split if:** the home-console UI card becomes part of this packet
  (it is a follow-on, P4-style), or Magic Kitty starts auto-acting on
  connections (it only surfaces; it never executes).
- **Do not expand into:** the next-step navigator (016), project registry CRUD
  (021), or any new LLM summarization inside `project_resume` (021's no-LLM
  guarantee).

## Privacy / sensitivity

- **Touches sensitive content?** yes — it aggregates `resume()` across ALL
  projects, including `kind="admin"` / `benefits-admin`, whose `summary` can
  contain `health_admin` content (D10 `PRIVACY_LOCAL_ONLY`).
- **Content classes:** `health_admin`, `none` (mixed — any non-code project may
  carry a local-only class).
- **Cloud allowed?** no. Cross-project synthesis must stay local-tier. The call
  uses `privacy_tier="local"` and `content_class="health_admin"` so the route
  fails toward privacy, never toward a cloud leak. It is fed through LiteLLM
  (`kitty-default`, a free model — DeepSeek Flash on the OpenRouter fallback),
  never a premium endpoint.
- **Forbidden:** never pass `privacy_tier="cloud_ok"` for cross-project
  synthesis; never send `benefits-admin` content to a cloud provider; never log
  raw project summaries at info level.

## Files likely touched

- `docs/packets/022-magic-kitty.md` (this file, new)
- `gateway/magic_kitty.py` (privacy hardening on the existing `call_llm`)
- `tests/test_magic_kitty.py` (assert captured privacy kwargs with fake data)
- `docs/packets/README.md` (registry row → `active_packet` / 🚧)

## Files not to touch

- `gateway/project_store.py` / `gateway/project_resume.py` schemas — 021 owns
  these; Magic Kitty is a consumer only.
- `gateway/llm_client.py` internals — call `call_llm()`, don't change the
  privacy boundary or add a provider.
- `gateway/next_step.py` — separate packet (016).
- `tutor*` files, `docs/tutor-design.md`, `.env`/secrets, the kitty submodule,
  `docs/plans/fix-council-ux-all.md`.

## Implementation sketch

1. `discover_connections(force=False)` (already present) lists active projects
   (falls back to all if none are active), builds each one's `resume()`, and
   if there are ≥2 resumes, feeds them to an LLM with a "find non-obvious
   connections" prompt. Results cache for 5 minutes; `force=true` bypasses.
2. The LLM call uses `model="kitty-default"` (free model) and MUST pass
   `privacy_tier="local"`, `content_class="health_admin"` (fail toward privacy,
   since the aggregate can include benefits content). This is the one-line
   hardening this packet adds on top of the existing shipped code.
3. `gateway/routes/magic.py` exposes `GET /magic` (and `?force=`) wired through
   `gateway/routes/register.py` — already registered.

## Acceptance criteria

1. `GET /magic` returns a dict with `connections` (list), `generated_at`, and
   `projects_used`; with <2 projects it returns an empty `connections` list and
   does not call the LLM.
2. With ≥2 fake `resume()` states the LLM is called once and the parsed
   connections are returned (array form, `insight_id` assigned when missing).
3. The `call_llm` call passes `privacy_tier="local"` and a non-None
   `content_class` — asserted via captured kwargs in the test (mirrors 016's
   privacy acceptance), so a cloud leak is structurally impossible for this
   route.
4. An LLM failure is raised loud (no silently-empty cache); a resume failure for
   any project raises a clear `RuntimeError` naming the project (Prime
   Directive: fail loud, never mask).
5. Caching holds: two calls within 5 minutes hit the LLM once; `force=true`
   regenerates.
6. Existing move-in bar work is not delayed (this is Wave 5 depth, after move-in).

## Verification commands

```bash
python3.12 -m pytest tests/test_magic_kitty.py -q
python3.12 -c "import gateway.routes.magic, gateway.magic_kitty; print('magic route imports OK')"
python3.12 -c "from gateway.routes.register import register_routes; from fastapi import FastAPI; app=FastAPI(); register_routes(app); print('/magic' in [r.path for r in app.routes])"
```

## Review artifacts

- `pytest` output (6 passed) — see PR body.
- Import / registration smoke checks above.

## Jacob review questions

1. Should the home console get a "Magic Kitty" card (follow-on), or is the
   `/magic` API + brief integration enough for now?
2. How aggressive should connections be — only high-confidence (≥0.7) "huh"
   moments, or surface weaker pattern hints too?

## One-line build instruction

Author this packet as the executor contract for the already-shipped
`/magic` cross-project synthesis, harden its `call_llm` to `privacy_tier="local"`
+ `content_class="health_admin"` so benefits content never leaves the local
tier, and prove it with fake-resume tests — do not rebuild the route or touch
021/016.
