# Packet 005 — Mail read-only connector (Gmail API)

- **Status:** ready — §16.2 decided 2026-07-02: **Gmail API, read-only**
  (D11 in `docs/DECISIONS.md`). Privacy boundary (packet 012 / D10) shipped,
  so `mail_body` routing enforcement already exists.
- **Best executor:** Codex or Claude Code for code. **Jacob himself** does
  the Google Cloud project + OAuth consent + first token grant — credentials
  are never an agent task. The agent's job ends at "reads token from disk."
- **Purpose:** Connect the highest-signal external feed, read-only, into the
  signal store. Mail becomes rows in `signals`; triage and the brief consume
  them like everything else.

## Decisions already made (do not reopen)

- **Provider:** Gmail API, scope exactly `https://www.googleapis.com/auth/gmail.readonly`.
  No send, no modify, no labels scope. (D11)
- **Bodies are local-only.** The signal payload carries sender / subject /
  snippet only. Full bodies are fetched on explicit demand and are data
  class `mail_body` under D10 — `llm_client.call_llm` already raises if a
  local-only class is routed to cloud. Never put a body in a signal row.
- **Connector shape (§17.2):** cron-polled adapter emitting deduped signal
  rows via `gateway/signal_store.emit()`. No webhooks, no push, no
  per-connector table.
- **HTTP stack:** `google-auth` + `google-auth-oauthlib` for the token dance
  (small, focused libs — add to `requirements.txt`), plain `requests` for
  the two REST calls (`users.messages.list`, `users.messages.get`). Do NOT
  add `google-api-python-client` (discovery client + httplib2 for two
  endpoints is not worth it).
- **Credentials on disk:** OAuth client secret path via env var
  `GMAIL_CLIENT_SECRET_FILE`, token cache at `data/gmail_token.json`
  (confirm `data/` is gitignored before writing anything there; it is today).
  Both documented in `.env` — keys live in `~/Projects/kitty/.env`, nowhere
  else.

## Exact scope

1. **New `gateway/connectors/__init__.py` + `gateway/connectors/mail.py`:**
   - A transport class wrapping the two Gmail REST calls, taking credentials
     via constructor injection so tests never touch the network.
   - `poll()` — list messages newer than the last poll (Gmail `q` filter,
     e.g. `newer_than:1d` on first run; thereafter use the newest seen
     `internalDate`), then for each new message emit:
     `signal_store.emit(source="mail", kind="mail.message",
payload={"from": ..., "subject": ..., "snippet": ..., "message_id": ...},
dedupe_key="mail:<gmail-message-id>")` — `emit()` already returns `None`
     on a dedupe hit; count and log hits vs new.
   - Gmail's `snippet` field is the payload snippet — never `payload.body`.
   - `fetch_body(message_id) -> str` — on-demand full body (format=full,
     decode base64url parts, text/plain preferred). Docstring must state:
     return value is data class `mail_body`, local-only under D10.
   - **Fail loud:** missing token file, expired-beyond-refresh token, or a
     non-200 from Google raises a typed error — never return `[]` as if the
     mailbox were quiet.
2. **Cron registration:** in the `gateway/app.py` startup block that already
   does `register_action("brief.refresh", ...)` etc., add
   `register_action("mail.poll", _action_poll_mail)`. Follow the existing
   pattern exactly; the schedule row itself is created the same way the
   existing actions' schedules are (look at how `brief.refresh` gets its
   schedule; mirror it — suggested default: every 15 minutes).
   If the token/env is absent, the action logs one warning per run and
   returns — a not-yet-configured connector must not crash the cron runner,
   but it must also surface in doctor (next item), not vanish.
3. **Doctor check:** in `gateway/doctor.py`, following the existing
   `Check(...)` pattern: `PASS connector:mail` when the token file exists,
   loads, and (cheaply) looks refreshable; `WARN` when unconfigured (no env
   var / no token — this is the pre-OAuth state, not an error); `FAIL` when
   configured but broken (unreadable token, refresh fails).
4. **Triage:** confirm mail signals flow into triage the same way other
   signal sources do. If triage needs more than a trivial mapping entry,
   STOP and split a packet.

## Jacob's personal setup task (blocks live verification, not the PR)

Create a Google Cloud project → enable Gmail API → OAuth consent (external,
test-user = his own account) → download the client secret JSON → set
`GMAIL_CLIENT_SECRET_FILE` in `.env` → run the one-time consent flow (ship a
tiny `python -m gateway.connectors.mail --auth` entry point for this) →
token lands in `data/gmail_token.json`. The packet's PR merges on
mocked-transport tests; the live poll is verified on his machine after.

## Files likely touched

- `gateway/connectors/__init__.py`, `gateway/connectors/mail.py` (new)
- `gateway/app.py` (one `register_action` line + one action fn)
- `gateway/doctor.py` (one check)
- `tests/test_mail_connector.py` (new — mocked transport)
- `requirements.txt` (`google-auth`, `google-auth-oauthlib`)
- `.env.example` / env docs if present

## Files not to touch

- `gateway/action_queue.py` and `config/action_tiers.json` — **no
  `email.send` kind exists after this packet.** Reply drafting is a later
  packet using the existing `note.draft` T1 kind.
- `gateway/llm_client.py` — D10 enforcement already shipped (packet 012).
- `gateway/signal_store.py` — consume `emit()`, don't extend it.
- Auth/secrets handling beyond the two documented env/file paths.

## Acceptance criteria

- Mocked-transport tests prove: signal shape (source/kind/payload keys/
  dedupe_key format), dedupe on re-poll (second poll of same messages emits
  0), snippet-only payload (assert `"body"` not in payload and payload under
  `signal_store.MAX_PAYLOAD_BYTES`), fail-loud on transport error (raises,
  not `[]`), unconfigured cron action logs-and-returns.
- `./kitty doctor --json` includes a `connector:mail` check in all three
  states (test the check function directly for PASS/WARN/FAIL).
- `fetch_body` docstring names the `mail_body` D10 class; a test asserts a
  body string never appears in any emitted signal payload.
- Full suite green: `python3.12 -m pytest tests/ -q --tb=short`.
- After Jacob's OAuth: one real poll on his machine produces mail signals
  visible in `/state/now`'s signals section — manual, post-merge.

## Verification

```bash
python3.12 -m pytest tests/test_mail_connector.py tests/ -q --tb=short
./kitty doctor --json | python3.12 -c "import json,sys; print([c for c in json.load(sys.stdin)['checks'] if 'mail' in c['name']])"
```

## Risks / rollback

- **Privacy:** snippet-only signals; bodies on demand, local-only (D10
  enforcement already live). Scope is read-only at the OAuth level — Google
  rejects anything else even if code regressed.
- **Volume:** poll window + dedupe cap the table; `MAX_PAYLOAD_BYTES`
  already guards row size.
- **Rollback:** disable the cron schedule row (`/cron` routes or DB), revert
  PR; existing signal rows are inert.

## Too broad if

It sends or modifies anything, auto-archives, adds a second provider,
builds reply drafting, or touches the tier sheet.

## Jacob reviews

- The exact payload fields landing in signals (before merge).
- The scopes requested in the consent screen (during his setup).
