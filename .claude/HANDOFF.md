# Session Handoff — 2026-07-04 (two parallel sessions)

## Session A: Fable plan session

- Branch: `claude/kitty-app-packet-plan-gs7ccc`, PR #97
- Request: "Plan the entire rest of the kitty app as packets" — done via
  live Q&A with Jacob, not doc archaeology.

### Done

- Packets 015–020 authored (`docs/packets/`): 015 phone channel
  (executor-ready, includes live-verified iMessage `participant` syntax),
  016 next-step navigator, 017 benefits rails + urgent-thing sweep,
  018 expert packs, 019 job search (⏸ parked), 020 GitHub connector.
- `docs/packets/README.md` rewritten: status legend (📋 spec ≠ ✅ built),
  the **move-in bar**, wave order 0–5.
- `docs/DECISIONS.md`: D12 (phone-first delivery + move-in bar).
- Walked Jacob through Wave 0 live: ethernet verified, Automation
  permission granted, iMessage-to-self proven end-to-end.

### Gotchas

- Jacob believes things are "done" when a spec exists — answer status
  questions with the README legend's words (built vs spec'd).
- All review artifacts must be PUSHED to his phone (D12); never ask him
  to go look at anything.
- Read `.claude/STATE.md` "Facts from Jacob" before talking to him — it
  explains the tone this project now requires.

## Session B: opencode (claimed 005 + 007)

- Original request: "Start nailing off the packets. Mark them done so
  multiple agents don't duplicate."
- Branch: main (claims), `feat/packet-005-mail-connector` (code)

### Done

- **Claim mechanism**: two-row update in `docs/packets/README.md` +
  `.claude/STATE.md`, pushed to main FIRST before code work.
- **Packet 005** built — PR #99 (`gateway/connectors/{__init__,mail}.py`,
  doctor `connector:mail` check, google-auth + google-auth-oauthlib in
  requirements, 25 mocked-transport tests + 4 doctor-state tests).
  - D10 enforced: signal payload carries only
    `{message_id, from, subject, snippet, internal_date}`; body never
    lands in a signal row (asserted by test).
  - Fail-loud: missing token / expired-no-refresh / non-200 raise typed
    errors; unconfigured `poll_now` returns `{skipped: "unconfigured"}`.
  - Verification: 100/100 across affected modules; ruff check+format clean.
- **Packet 007** — shipped by Jacob directly to main (eb3afad) while the
  session ran; the 007 worktree was discarded to avoid a competing PR
  (the claim mechanism working as intended).
- **Did not modify `docs/AGENT_HANDOFF.md`** — the global hook
  `~/.claude/hooks/handoff-snapshot.sh` keeps rewriting it; dual-source
  mismatch still unfixed. Coordination via STATE.md + registry instead.

## Next actions (combined)

1. Review PR #99 (005); merge after green check runs; mark shipped in
   registry (chore commit on main).
2. Merge PR #97 (the plan) once CI green and Jacob approves.
3. Jacob's Wave-0 tail: `PUSH_IMESSAGE_RECIPIENT` in `.env`,
   `./kitty up` + `./kitty doctor`, confirm `data/gmail_token.json`.
4. First free executor builds **015** (claim in STATE.md first). Codex is
   on 008-remainder in `.worktrees/packet-008-expert-retrieval` — check
   `git worktree list` before claiming anything.
5. Optional / awaiting Jacob: fix the handoff-snapshot.sh dual-source
   mismatch.
