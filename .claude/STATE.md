# STATE — Kitty

> Live packet coordination. Read before picking up work. Update when claiming or finishing.

## Goal

Execute open implementation packets without duplicate agent work.

## Branch

main

## Sessions

- 2026-07-04 — opencode session claiming **005** + **007**. Order:
  005 first (per registry), then 007. Each on its own worktree off
  `origin/main`. This row exists so other agents can see the claim
  before they pick the same packet.
- 2026-07-04 — Fable plan session (branch
  `claude/kitty-app-packet-plan-gs7ccc`, PR #97): H1 close-out plan,
  packets 015–020, move-in bar, D12. Also walked Jacob through Wave 0
  live — see "Facts from Jacob" below.

## Packet claims

| Packet        | Claimed by          | Status                         |
| ------------- | ------------------- | ------------------------------ |
| 005           | opencode 2026-07-04 | 🚧 in progress (worktree soon) |
| 007           | opencode 2026-07-04 | 🚧 in progress (after 005)     |
| 008-remainder | —                   | available                      |
| 015           | —                   | available — **next priority** (D12: phone channel before features) |

**Rule for other agents:** if the status above is anything other than
`available`, the packet is taken. Pick another. If you need to release a
claim, edit this row to `available` and commit to `main`.

## Done this session

- 004 shipped (#98) — HomeState console replaces DashboardHome.
- Plan PR #97 (packets 015–020 + D12 + move-in bar).
- Wave 0 (Jacob, live): ethernet in + verified; Automation permission
  granted; **iMessage-to-self proven end-to-end** — `participant … of
  (1st account whose service type = iMessage)` works, `buddy` fails
  silently. Banked in packet 015.

## In flight

- 005 — implementing `gateway/connectors/mail.py`, cron registration,
  doctor check, mocked-transport tests. No code yet on disk.

## Blocked on Jacob

- Wave-0 tail: `PUSH_IMESSAGE_RECIPIENT` in `.env`, `./kitty up` +
  `./kitty doctor`, confirm `data/gmail_token.json` exists (he reports
  the OAuth flow was completed the morning of 2026-07-04 — the `ls` is
  the verification, don't re-run the flow blind).

## Facts from Jacob (2026-07-04, load-bearing — read before talking to him)

- He has **never used Kitty** and won't before the move-in bar
  (`docs/packets/README.md`) is met. He is phone-first; iOS pushes are
  the only channel that works (D12). Telegram and email are dead ends.
- All review artifacts must be PUSHED to his phone — "show me, I'm not
  gonna go looking for this." Never assume he opens an app unprompted.
- He conflates "spec exists" with "built" — answer status questions with
  the registry legend's words. The tier sheet = "the permission slip,"
  signed 2026-07-02.
- Missed the student-loan repayment-assistance deadline in June (~$600) —
  the trigger for packet 017. When asked what's urgent in the next 60
  days: "there's something urgent. I don't know what it is."
- Disability (SAID/CDB/DTC) is the income track; job search parked (019).
  No résumé, 10 years out of work. Personal context is rough (housing
  precarity mentioned, substance use disclosed). Stance: operator's
  situational awareness, zero lecturing, per SOUL + D9. Recovery expert
  pack is strictly opt-in and Kitty does not raise it.
- Kitty's house: the broken-screen MacBook Air, headless, on ethernet.

## Next actions

1. opencode: worktree `feat/packet-005-mail-connector` off `origin/main`,
   implement, PR, merge, mark shipped; then same for 007.
2. Merge PR #97 (the plan) once CI is green and Jacob approves.
3. First free executor: build 015 (claim it here first).
4. Write `.claude/HANDOFF.md` end-of-session.
