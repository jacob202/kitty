# Packet 017 — Benefits/admin rails + the urgent-thing sweep

- **Status:** 🚧 claimed — executor-ready (authored 2026-07-06).
- **Claimed by:** opencode 2026-07-06.
- **Best executor:** Claude Code (privacy-boundary care); deadline-extraction
  prompt reviewed by strongest model before merge.
- **Purpose:** Two jobs. (1) **Rails:** any letter, form, or PDF Jacob
  photographs or forwards becomes an ingested document with extracted dates,
  and every date becomes a watched deadline that escalates to his phone. (2)
  **The sweep:** a first-run discovery pass over everything reachable — Gmail
  signals, ingested docs, existing deadline rows — that answers "what is the
  urgent thing?" and pushes the answer to him.

## Decisions already made (do not reopen)

- **Phone-first delivery** via `gateway.push.push_to_jacob` (D12, packet 015).
  Escalations are pushes, not action-queue rows.
- **Local-only for private content.** Extraction over letters, mail bodies, and
  health/admin documents runs with `privacy_tier="local"`,
  `content_class="health_admin"`. Cloud routing must be rejected by D10.
- **One `benefits-admin` project.** Non-code, seeded automatically alongside the
  kitty repo project. It is the OPERATOR_STRATEGY test that Kitty is not
  secretly a dev tool.
- **No auto-submission, no eligibility research engine, no second recipient.**
  v1 is rails only: watch, warn, surface. (See "Too broad if".)
- **Escalation cadence: T-7d / T-3d / T-1d / day-of.** Each deadline pushes at
  most once per checkpoint. Dedupe keys are stable.

## Exact scope

1. **Seed the `benefits-admin` project.** In `gateway/project_store.py`, extend
   `_seed_kitty_project_once()` (or add a new `_seed_benefits_project_once()`)
   to register project id 2 with `name="benefits-admin"`, `kind="admin"`,
   `status="active"`. Idempotent via a new `app_settings` key.
2. **New migration `gateway/migrations/013_deadlines.sql`.**
   - `deadlines` table: `id`, `project_id` (FK → benefits-admin), `source`
     (e.g. `knowledge:letter_2026_06_20.pdf` or `mail:msg_abc123`),
     `source_id` (optional opaque reference), `due_date` (ISO date string),
     `obligation` (text), `amount` (text, optional), `currency` (text,
     optional), `confidence` (`high|medium|low|needs_jacob`), `status`
     (`open|closed|needs_jacob`), `dedupe_key` (UNIQUE), `created_at`,
     `updated_at`, `pushed_at` (last escalation push timestamp).
   - `deadline_escalations` table: `id`, `deadline_id`, `checkpoint`
     (`T-7d|T-3d|T-1d|day-of`), `pushed_at`, `dedupe_key` (UNIQUE). One row per
     actual push so a checkpoint never fires twice.
3. **New `gateway/deadline_extractor.py`.**
   - `extract_from_text(text: str, *, source: str, source_id: str | None = None,
     llm_fn=None) -> list[dict]` — calls a local model (injected `llm_fn` for
     tests) with `privacy_tier="local"`, `content_class="health_admin"` and
     returns a list of deadline dicts. Low-confidence or ambiguous items are
     returned with `confidence="needs_jacob"`; nothing is dropped silently.
   - `extract_from_document(source: str, text: str, *, llm_fn=None) -> list[dict]`
     — thin wrapper that builds a stable `dedupe_key` from source + date +
     obligation hash.
   - `extract_from_mail_signal(signal: dict, *, llm_fn=None) -> list[dict]` —
     reads `signal["payload"]`; only processes signals where
     `signal["source"] == "mail"` and `kind` in `{"deadline", "admin"}` (or
     lacking a kind, any signal with date-like content). Returns the same shape.
   - Prompt returns **only** JSON: `[{"due_date": "YYYY-MM-DD",
     "obligation": "...", "amount": "...", "currency": "...",
     "confidence": "high|medium|low|needs_jacob", "notes": "..."}]`.
     Malformed JSON or missing dates ⇒ raise `DeadlineExtractorError` with the
     raw snippet; callers log and surface `needs_jacob`.
4. **New `gateway/deadline_store.py`.**
   - `upsert(deadline: dict) -> dict` — insert or update by `dedupe_key`,
     returning the row. If `confidence == "needs_jacob"`, status is
     `needs_jacob`.
   - `list_open() -> list[dict]`, `list_needs_jacob() -> list[dict]`,
     `get(id) -> dict | None`, `close(id) -> dict`, `mark_pushed(id) -> None`.
   - `checkpoint_due(deadline: dict, now: date) -> str | None` — given a row,
     return the escalation checkpoint that should fire today, or `None`.
   - `record_escalation(deadline_id, checkpoint) -> None` — insert into
     `deadline_escalations`.
5. **New `gateway/deadline_watch.py`.**
   - `check_and_push(now=None, push_fn=None) -> dict` — called by cron daily.
     For each open deadline whose `due_date` is within 7 days (or overdue):
     compute checkpoint, skip if already recorded, otherwise call
     `push_to_jacob(..., kind="alert", title="Deadline", dedupe_key=...)` and
     record escalation. Return counts `{checked, pushed, skipped}`.
   - Never push for deadlines with `status="needs_jacob"`; those are surfaced
     only by the sweep.
6. **New `gateway/routes/deadlines.py`.**
   - `GET /deadlines` — list open deadlines (optionally `?status=needs_jacob`).
   - `GET /deadlines/{id}` — single deadline.
   - `POST /deadlines/{id}/close` — close a deadline (Jacob reviewed / handled).
   - `POST /deadlines/sweep` — run the urgent-thing sweep and return the report
     (does not push by default; see query param).
   - `POST /deadlines/sweep?push=1` — run sweep and push the report to Jacob.
7. **The urgent-thing sweep (`gateway/deadline_sweep.py`).**
   - `sweep(*, push_fn=None) -> dict` — gather:
     - All open deadlines sorted by `due_date` ascending.
     - Recent mail signals (last 90 days) not yet associated with a deadline.
     - Recent knowledge document sources tagged `doc_type` in
       `{"letter", "form", "statement", "bill"}` or `collection == "benefits"`.
   - For each unprocessed mail/doc source, call `deadline_extractor` and upsert
     any found deadlines.
   - Rank results by a simple score: `score = days_until_due_inverse *
     amount_weight * confidence_weight`. Near dates and high amounts rank
     higher. Exact formula is an implementation detail; the test asserts that a
     near-dated high-amount item ranks above a far-dated low-amount item.
   - **Blind spots:** explicitly report what could not be seen: no Gmail token,
     empty knowledge base, mail connector unconfigured, etc. An empty report
     must say why it is empty.
   - Report shape: `{found: [...], blind_spots: [...], top: {...}, generated_at}`.
   - If `push_fn` provided, push a 3-line summary with title "Urgent-thing
     sweep" and dedupe key `sweep-{date}`.
8. **Wire into `gateway/brief.py`.** Add a `get_deadlines_section()` that returns
   up to 3 open deadlines (nearest first, high confidence before
   `needs_jacob`). Render them in `brief_scheduler._format_brief_text` under a
   "Deadlines" bullet.
9. **Launcher subcommand.** `./kitty sweep` runs `deadline_sweep.sweep(push_fn=
   push_to_jacob)` and prints the report.
10. **Doctor check.** `deadlines:watch` — PASS when at least one open deadline
    exists and the last escalation push (if any) succeeded; WARN when no
    deadlines are being watched; FAIL when the last push attempt failed. Add
    to `gateway/doctor.py` following the existing `Check(level, name, detail)`
    pattern.
11. **Env docs.** Add `PUSH_IMESSAGE_RECIPIENT` / `PUSHOVER_*` reminder to
    `hermes.env.example` if not already present (they should be from 015).
    Document that deadline extraction is local-only.

## Files likely touched

- New: `gateway/deadline_extractor.py`, `gateway/deadline_store.py`,
  `gateway/deadline_watch.py`, `gateway/deadline_sweep.py`,
  `gateway/routes/deadlines.py`, `gateway/migrations/013_deadlines.sql`,
  `tests/test_deadline_extractor.py`, `tests/test_deadline_store.py`,
  `tests/test_deadline_watch.py`, `tests/test_deadline_sweep.py`,
  `tests/test_deadlines_routes.py`.
- Edits: `gateway/project_store.py` (seed benefits-admin project),
  `gateway/brief.py` (deadlines section), `gateway/brief_scheduler.py`
  (render deadlines), `gateway/doctor.py` (deadlines:watch check),
  `kitty` launcher (sweep subcommand), `docs/packets/017-benefits-rails-urgent-sweep.md`
  (this file, updated to ✅ shipped after merge),
  `docs/packets/README.md` (registry update).

## Files not to touch

- `gateway/llm_client.py` boundary already exists; do not weaken D10.
- `gateway/mail.py` / connector internals — read signals, do not modify.
- `gateway/action_queue.py` — pushes are deliveries, not actions.
- `gateway/notify.py` — use `push.py`.
- Do not add eligibility research, form auto-submission, or email-outbound.

## Steps

1. Migration + store layer + unit tests (no LLM, no push).
2. Extractor module with injected `llm_fn` + privacy-boundary tests.
3. Watch cron function + escalation tests (stub `push_fn`).
4. Sweep module + ranking/blind-spot tests.
5. Routes + launcher + doctor + brief integration + env docs.
6. Full suite green.

## Acceptance

- A fixture PDF text with a buried deadline produces a deadline row with
  `confidence=high`, stable dedupe key, and `status=open`.
- A low-confidence/ambiguous text produces `confidence=needs_jacob` and
  `status=needs_jacob`; it is not pushed by the watch cron.
- Watch cron fires at exactly the T-7/T-3/T-1/day-of checkpoints; no
  checkpoint fires twice for the same deadline.
- The sweep ranks a near-dated, high-amount fixture above a far-dated,
  low-amount fixture and reports blind spots when sources are missing.
- D10: extracting from `health_admin` content with a cloud-tier stub raises
  `PrivacyBoundaryError` before any provider is contacted
  (`tests/test_llm_privacy_boundary.py` pattern extended).
- Brief includes up to 3 open deadlines ordered by due date.
- `./kitty sweep` prints a report and pushes when configured.
- `python3.12 -m pytest tests/ -q --tb=short` passes.

## Verification commands

- `python3.12 -m pytest tests/test_deadline_*.py tests/test_llm_privacy_boundary.py -q --tb=short`
- `python3.12 -m pytest tests/ -q --tb=short`
- `./kitty sweep` (on the Air, with push configured)
- `./kitty doctor --json | python3.12 -m json.tool` (see `deadlines:watch`)

## Risks

- **Extractor hallucinates dates.** Mitigation: confidence scoring,
  `needs_jacob` bucket, no silent drops.
- **Privacy boundary leak.** Mitigation: every extractor call tags
  `content_class="health_admin"` and `privacy_tier="local"`; tests patch the
  provider chain to explode on cloud routing.
- **Notification spam.** Mitigation: one push per checkpoint per deadline,
  dedupe keys, `needs_jacob` items excluded from auto-escalation.
- **Empty sweep feels safe when it isn't.** Mitigation: explicit blind-spot
  list in every report.

## Rollback

- Revert the PR.
- Drop tables from migration 013 (or leave them empty; they are inert).
- Benefits-admin project row is harmless; brief simply stops reading deadlines.

## Unlocks

- Move-in bar item 3: benefits/admin paper watched with escalating deadline
  alerts.
- Future packets can call `deadline_store.close()` when Jacob handles a
  deadline, and `deadline_extractor` for new document types.

## Too broad if

- It auto-submits forms, emails agencies, or researches eligibility.
- It grows a notification-preferences UI or per-deadline cadence editor.
- It adds two-way command parsing over iMessage.

## Jacob reviews

- First live sweep report: is the ranking right? Anything real missing?
- Escalation cadence: T-7/3/1/day-of — help or nagging?
- Confirm he is comfortable with the local-only extraction of photographed
  letters (no cloud).
