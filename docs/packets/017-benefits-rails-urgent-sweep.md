# Packet 017 — Benefits/admin rails + the urgent-thing sweep

- **Status:** 📋 spec authored 2026-07-05, executor-ready — the Wave 4 packet;
  end of this packet = move-in day.
- **Best executor:** Claude Code (privacy-boundary care); deadline-extraction
  prompt reviewed by strongest model before first live run.
- **Stakes, so nobody scopes this down:** Jacob missed the student-loan
  repayment-assistance deadline in June 2026 and it cost him ~$600 he didn't
  have. When asked what's urgent in the next 60 days he answered: *"there's
  something urgent. I don't know what it is."* This packet exists so that
  sentence can never be true silently again.
- **Purpose:** Two jobs. (1) **Rails:** any letter, form, or PDF Jacob
  photographs or forwards becomes an ingested document with extracted dates,
  and every date becomes a watched deadline that escalates to his phone.
  (2) **The sweep:** a first-run discovery pass over everything reachable —
  mail signals, ingested docs — that answers "what is the urgent thing?" and
  pushes the answer, including what it could NOT see.

## What already exists (verified against the code 2026-07-05, do not rebuild)

- **Capture:** `gateway/knowledge.py` `ingest()` (async) and
  `gateway/pdf_pipeline.py` `extract_pdf_enhanced(path) -> list[PdfChunk]`
  (010, #74). Documents already flow in; this packet reads what lands.
- **Signals:** `gateway/signal_store.py` —
  `emit(source, kind, payload=None, dedupe_key=None, ts=None)`,
  `list_recent(limit, source=None)`, `mark_processed(id)`. Payload cap 16 KB.
- **Cron:** `gateway/cron.py` — `register_action(name, async_fn)` +
  `schedule(name, action, cron_expr, metadata)`; runner starts with the
  gateway. This is where the daily deadline check lives.
- **Push:** `gateway/push.py` `push_to_jacob(message, *, kind="info"|"alert",
  title, url=None, dedupe_key=None) -> bool` (015). Quiet hours + 24h dedupe
  are already handled there — do not reimplement either.
- **Mail:** `gateway/connectors/mail.py` (005) — read-only Gmail; token
  verified live on Jacob's Air 2026-07-05. Mail *bodies* are `mail_body`
  (D10 local-only); headers/subjects arrive as signals.
- **Projects + B:** `project_store` / `project_resume` / `next_step` (021 +
  016). The benefits project registers through the normal API — zero special
  cases in project code.
- **LLM privacy seam:** `call_llm(..., privacy_tier="local",
  content_class="health_admin")` — `PRIVACY_LOCAL_ONLY` already contains
  `health_admin` and `mail_body`; `enforce_privacy_boundary` raises on
  violation. `next_step.py` shows the injected-`llm_fn` test pattern to copy.
- Migrations 001–011 are taken. **This packet's migration is `012_deadlines.sql`.**

## Exact scope

1. **Migration `012_deadlines.sql`** — one table:

   ```sql
   CREATE TABLE IF NOT EXISTS deadlines (
       id INTEGER PRIMARY KEY AUTOINCREMENT,
       created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
       due_date TEXT NOT NULL,              -- ISO date; date-only is fine
       obligation TEXT NOT NULL,            -- "SAID renewal form B", human words
       amount REAL,                         -- NULL when no dollar figure
       source_kind TEXT NOT NULL,           -- 'document' | 'mail' | 'manual'
       source_ref TEXT NOT NULL DEFAULT '', -- doc path / signal id / ''
       confidence TEXT NOT NULL DEFAULT 'high',  -- 'high' | 'low'
       status TEXT NOT NULL DEFAULT 'open', -- 'open' | 'done' | 'dismissed'
       closed_at REAL,
       dedupe_key TEXT UNIQUE               -- hash(due_date + obligation)
   );
   ```

   One row per obligation. Escalation state is NOT stored here — push.py's
   dedupe (key `deadline-{id}-{days_out}`) already makes each rung fire once.

2. **`gateway/deadline_store.py`** — D7 store: `create()`, `get()`,
   `list_open(within_days=None)`, `close(id, status)`, typed errors
   (`DeadlineError`/`DeadlineNotFound`), `_row_to_deadline()`, `init_db()`.
   Low-confidence extractions are stored with `confidence='low'` AND emitted
   as a `needs_jacob`-bucket triage entry — never silently dropped, never
   silently trusted.

3. **`gateway/deadline_extractor.py`** — the only LLM surface in this packet.
   `extract(text, source_kind, source_ref, llm_fn=None) -> list[dict]`:
   prompts a **local** model (`privacy_tier="local"`,
   `content_class="health_admin"`) for `[{due_date, obligation, amount,
   confidence}]`, JSON-only response, same `LlmFn` seam as `triage.py`/
   `next_step.py`. Unparseable model output raises `ExtractionError` (fail
   loud); an empty list is a valid answer. Then `deadline_store.create()`
   per tuple + `signal_store.emit("deadlines", "deadline_found", payload,
   dedupe_key)` so the state spine sees it.

4. **Wiring into capture:** after 010's ingestion completes for a document
   classified `health_admin` (and for new mail signals), run the extractor.
   Keep the hook minimal: one call site per pipeline, behind
   `DEADLINE_EXTRACTION_ENABLED=1` (default on) so a bad prompt can be
   switched off without a deploy.

5. **Deadline watch cron:** `register_action("deadline_watch", ...)` +
   default schedule daily 09:00 local. For each `list_open(within_days=8)`
   row, push at T-7d / T-3d / T-1d / day-of: `kind="info"` at T-7/T-3,
   `kind="alert"` at T-1/day-of (alert bypasses quiet hours — that's 015's
   documented contract, on purpose here). Message names the obligation, the
   date, the amount when known, and how to close it.

6. **The sweep — `POST /sweep/urgent` + `./kitty sweep`:** one pass over
   (a) open deadlines, (b) recent mail signals (60 days), (c) knowledge
   inventory for `health_admin` docs. Rank mechanically: proximity buckets
   (overdue / ≤7d / ≤30d / ≤60d) then amount desc then confidence — **no LLM
   in the ranking**, so the sweep works even when models are down. Output is
   one report: ranked items, each with source + date + amount, followed by a
   mandatory **blind-spots section** built from real checks (no Gmail token →
   say so; zero `health_admin` docs ingested → say so; extraction disabled →
   say so). Push the report via 015 and return it from the route. An empty
   list with no named blind spots is a bug by definition.

7. **Benefits project:** seed nothing in code. The packet's *runbook step*
   (Jacob or the executor, one command): `./kitty project add "benefits +
   admin" ~/Documents/benefits admin` — then 016 gives it a B like any other
   project. The disability track (SAID / CDB / DTC application states) lives
   in that project's `open_questions`/`next_actions` via normal PATCH calls.

8. **Routes:** `gateway/routes/deadlines.py` — `GET /deadlines` (open by
   default, `?status=` filter), `POST /deadlines` (manual add — Jacob knows
   dates no document states), `POST /deadlines/{id}/close`,
   `POST /sweep/urgent`. Register in `routes/register.py`. Launcher:
   `kitty deadlines` (list) and `kitty sweep` subcommands following the
   `cmd_project` pattern.

## Design calls (decided here so the executor doesn't re-litigate)

- **Escalation state via push dedupe keys, not DB columns.** 015 already
  guarantees once-per-24h per key; `deadline-{id}-{days_out}` makes each
  rung idempotent. A `pushes_sent` column would be a second source of truth.
- **Sweep ranking is mechanical.** The extractor may use a local LLM;
  the sweep may not. The safety net must not depend on model availability.
- **Low confidence ⇒ `needs_jacob`, high confidence ⇒ watched deadline.**
  Both paths keep the row; confidence only changes who confirms it.
- **Date-only granularity.** Deadlines are calendar obligations, not
  appointments. Times, when present, go in the obligation text.

## Files likely touched

- `gateway/migrations/012_deadlines.sql` (new)
- `gateway/deadline_store.py`, `gateway/deadline_extractor.py` (new)
- `gateway/routes/deadlines.py` (new) + `gateway/routes/register.py`
- `gateway/knowledge.py` or its ingestion call site (one hook), mail signal
  processing call site (one hook)
- `gateway/cron.py` consumer registration (wherever existing actions register)
- `kitty` launcher (`deadlines`, `sweep`)
- `tests/test_deadline_store.py`, `tests/test_deadline_extractor.py`,
  `tests/test_deadlines_routes.py`, `tests/test_sweep.py` (new);
  `tests/test_db.py` migration-list update
- `.env.example` (`DEADLINE_EXTRACTION_ENABLED`)

## Files NOT to touch

- `gateway/push.py`, `gateway/imessage.py` (015 is closed — consume only)
- `gateway/llm_client.py` (the privacy boundary is already correct; if it
  seems to need a change, the packet is wrong — stop)
- `gateway/next_step.py`, `gateway/project_*.py` (benefits is a normal
  project; special-casing it there is scope failure)

## Acceptance criteria (commands, not vibes)

- [ ] `./venv/bin/python -m pytest tests/ -q` green, including:
  - fixture text with a buried date + amount → extractor (stub `llm_fn`)
    → deadline row + `deadline_found` signal, end to end;
  - low-confidence extraction → `confidence='low'` row AND a `needs_jacob`
    triage entry;
  - cron action over a fixture deadline at T-7/T-3/T-1/T-0 produces pushes
    with the right kinds and dedupe keys (push façade stubbed, capture args);
  - sweep over fixtures ranks a near-dated high-amount item first and the
    report names at least one real blind spot when a source is absent;
  - privacy: extractor called with a cloud tier raises via
    `enforce_privacy_boundary` (extend the `test_llm_privacy_boundary.py`
    pattern — assert the call *fails*, don't just assert the arg).
- [ ] `ruff check` / `mypy` clean on new files.
- [ ] Manual, real gateway in the container: `./kitty sweep` with no Gmail
  token and an empty knowledge base prints a report whose items list is
  empty and whose blind-spots section names both gaps. That exact output
  pasted into the PR body.
- [ ] On Jacob's Air (his half): photograph one real letter, watch it become
  a deadline row, and receive the T-N push on his phone.

## Jacob reviews

- The first live sweep report — is anything real missing from it?
- Escalation cadence: does T-7/3/1/0 feel like help or nagging? (One knob:
  the cron schedule + rung list, both in one place.)

## Too broad if

- It auto-submits anything, emails anyone, or grows a benefits-eligibility
  research engine (eligibility research is a later packet — rails first).
- The extractor starts summarizing documents beyond date/obligation/amount.
- The sweep grows an LLM ranking pass. Mechanical or it doesn't ship.
