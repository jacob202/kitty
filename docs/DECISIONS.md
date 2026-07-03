# Decisions

**Date:** 2026-07-02
**Status:** Canonical forward-looking decision log. Historical detail remains in `docs/DECISIONS_AND_ROADMAP.md`.

## D1 - Local-First Single User

Kitty runs on Jacob's Mac for one user. No multi-tenant cloud architecture in the current roadmap.

## D2 - Gateway Is The Product

All clients stay thin. Product logic belongs in the FastAPI gateway, not Raycast, Telegram, Siri, or the Next.js UI.

## D3 - memory_graph Owns Context Reads

New prompt/search context reads go through `gateway/memory_graph.py`. Phase B may add a write-side router, but should not bypass this read rule.

## D4 - Keep Inbox JSONL For Capture

`data/inbox.jsonl` remains append-only and mobile-compatible. It is allowed to coexist with SQLite because capture must work even when richer app state is broken.

## D5 - Phase B Is Consolidation

Phase B is one storage story and one operating story. No mobile app, cloud sync, push notifications, full agent dashboard, TELOS expansion, or new memory substrate.

## D6 - Borrow Patterns, Not Random Complexity

Code sniping is encouraged when it maps to Kitty's current loop. Borrow proven UX and architecture patterns; do not import a repo's worldview wholesale.

## D7 - StorageRouter Is A Thin Write-Side Seam, Not A Port

`gateway/storage_router.py` (Phase B B4) is a deliberately thin write-side
seam that mirrors the read rule in D3. Routes cross it for mutations; the
underlying store modules do the actual work. The router does **not** try to
abstract the storage substrate, define a generic adapter registry, or hide
the backend.

Why: every prior attempt to build a backend-agnostic port (per-store
adapters, query language, hidden fallback) expanded the seam's surface
without earning anything back. A thin wrapper buys us "every write goes
through one module" at zero abstraction cost. The substrate can change
later if a real migration needs it; the seam does not pre-pay for that.

What this rules out:

- New methods on `storage_router` for stores that don't currently have a
  write seam (e.g. `desktop_store`, `token_usage_log`, `model_digest`).
- Generic `append`/`upsert`/`read` verbs that hide which backend is used.
- "Smart" router code that retries, caches, or falls back across backends.

What this allows:

- Wrapping any new write site in a one-line function that delegates to
  the underlying store, as B4 did for todos and plugin settings.
- Replacing the thin wrapper with a real port later if a migration needs
  it (the migration would be local; consumers would only change at the
  call site).

The chats migration (Phase C C0–C6) and the journal migration (Phase C
B0–B6) followed the same pattern but did **not** go through
`storage_router` — those are new read/write modules of their own. The
router is for legacy stores that already have a write API in
`todo_store` / `plugin_registry`; new modules get their own.

## D8 - Lint Is High-Signal Only; E501 Not Enforced

Ruff runs `select = ["E", "F", "W", "I"]` but ignores `E501` (line-too-long).
The repo runs no autoformatter, and ~87% of E501 violations are unwrappable
string literals (LLM prompts, URLs, error/log text); wrapping them hurts
readability for the lowest-signal rule in the set. The genuinely useful checks
(undefined names, unused imports, import order, ambiguous names) stay enforced.

Why: enforcing line length without a formatter produces churn, not safety. If a
formatter (`ruff format`) is adopted later, re-enable `E501` — the formatter
will handle the code lines and string literals can take targeted `# noqa`.

## D9 - Kitty Is A Personal Operating Layer

Adopted 2026-07-01 from `docs/OPERATOR_STRATEGY.md` (merged in #59).

Kitty's product identity is a personal operating layer: a state store,
capture-and-triage loop, action queue with enforced approval tiers, and
model-delegation router — worn with the SOUL persona. Chat is one interface
to that layer, not the product. The near-term build order is the state +
action spine (packets in `docs/packets/`), not further consolidation,
memory expansion, or UI polish.

What this rules out until the spine ships:

- New memory substrates, typed knowledge graphs, event buses.
- Autonomous outbound actions of any kind (draft-only until the action
  queue has audit history).
- Panels or endpoints that serve fabricated data; state surfaces bind to
  real rows or do not ship.

What this commits to:

- New state-spine stores (signals, triage, actions, projects) are each
  their own module over `kitty.db` migrations, per D7.
- External feeds are cron-polled connectors that emit deduped signal rows.
- Every action Kitty takes is a recorded row with a preview and a result;
  approval tiers are enforced in the executor registry, in code.

## D10 - Privacy Boundary In The LLM Router

Adopted 2026-07-02 from `docs/OPERATOR_STRATEGY.md` §17.3, via packet 012.

Local-first is the product thesis. That is not enforceable by convention once
cloud models do drafting — it has to be enforced in code at the call site
where journal, mail, and health/admin content enters the LLM pipeline.

**Data classes:**

| Class          | Default privacy | Examples                                           |
| -------------- | --------------- | -------------------------------------------------- |
| `journal`      | local-only      | journal entries, interview turns, dream synthesis  |
| `mail_body`    | local-only      | full email body, replies, attachments              |
| `health_admin` | local-only      | SAID/CDB/DTC docs, benefits letters, medical forms |
| `calendar`     | cloud-permitted | event titles, times, locations                     |
| `todo`         | cloud-permitted | todo text, action queue payloads                   |
| `chat`         | cloud-permitted | persona chat, triage classification                |

**Enforcement in `gateway/llm_client.py`:**

- `call_llm(..., privacy_tier: Literal["local","cloud_ok"] = "local",
content_class: str | None = None)`
- If `content_class` is in `PRIVACY_LOCAL_ONLY` and `privacy_tier == "cloud_ok"`,
  raise `PrivacyBoundaryError` with a reason. The route layer translates that
  to HTTP 400.
- Journal route tags `content_class="journal"` and defaults `privacy_tier="local"`.
- Any future route carrying private content MUST tag both fields. Routes
  that pass `content_class=None` keep the previous permissive behavior (any
  cloud model is acceptable) so existing call sites don't break, but new
  private-data call sites must opt in explicitly.

**What this rules out:**

- Mail and journal routes silently using cloud models.
- Bypassing the boundary by calling providers directly instead of through
  `call_llm`. The packet's audit found ~20 modules importing `llm_client`;
  a follow-up packet should grep for direct provider HTTP calls and route
  them through `call_llm`.

**What this commits to:**

- `gateway/llm_client.call_llm` is the only sanctioned entry point for LLM
  calls that may carry private content. New routes for mail, journal, and
  health/admin MUST go through it.
- `tests/test_llm_privacy_boundary.py` exists and asserts the journal case
  raises on cloud and the chat case does not.

## D11 - Mail Connector Uses The Gmail API, Read-Only

Decided by Jacob 2026-07-02 (§16.2 in `docs/OPERATOR_STRATEGY.md`).

The mail connector (packet 005) uses the **Gmail API, read-only scope** —
not Apple Mail via AppleScript.

**Why Gmail over AppleScript:** robust and scriptable vs brittle and
Mac-only. The tradeoff accepted: Google OAuth and a cloud API sit in the
read path.

**What this commits to:**

- Read-only scope (`gmail.readonly`). Sending stays off the table until the
  action queue has earned trust (per §16.2 — draft-only regardless of
  transport).
- Mail **bodies are `mail_body` class = local-only** under D10. The Gmail
  API fetches them, but they must not be routed to cloud LLMs. Fetching via
  Google was accepted; processing stays local.
- Connector shape follows §17.2: cron-polled adapter emitting deduped signal
  rows. No webhooks, no push.

**What this rules out:**

- AppleScript/Apple Mail integration for mail.
- Any write scope in v1 (send, label, archive, delete).
