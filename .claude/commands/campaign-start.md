---
name: campaign-start
description: Open a resumable campaign ledger for a long multi-phase task, then work phase 1
---

# Campaign start

Goal: `$ARGUMENTS`

A campaign is long work that will outlive this session. The ledger is the
durable state; this session is disposable. Assume you get killed mid-phase.

## 1. Plan the phases first — read only

Do not edit anything yet. Investigate, then decide the ordered phases. Each
phase needs **an exact command that proves it passed**. A phase whose proof is
"I read the code and it looks right" is not a phase — split it until every one
ends in a runnable command.

Narrow commands only. `venv/bin/python3.12 -m pytest tests/test_x.py -q` is a
phase gate; the full suite is not. The full suite belongs in the last phase.

## 2. Open the ledger

```bash
venv/bin/python3.12 scripts/campaign.py --slug <slug> init \
  --goal "<one sentence>" \
  --phase "reproduce::venv/bin/python3.12 -m pytest tests/test_x.py::test_bug -q" \
  --phase "fix::venv/bin/python3.12 -m pytest tests/test_x.py -q" \
  --phase "gate::venv/bin/python3.12 -m pytest tests/ -q"
```

`init` commits the ledger itself. Show Jacob the phase table before you start
phase 1.

## 3. Work one phase at a time

For each phase, in order:

1. Do the work.
2. Commit it with a scoped message. **Commit before verifying** — `verify`
   refuses on a dirty tree, by design: an unverified phase must not be able to
   claim a commit it does not own.
3. Run the gate:
   ```bash
   venv/bin/python3.12 scripts/campaign.py --slug <slug> verify <n>
   ```
4. Exit 0 means the ledger now records the phase as `verified` with the commit
   SHA, and that update is already committed. Exit 1 means NOT DONE — read the
   printed tail, fix, repeat.

Never hand-edit a status to `verified`. `campaign.py audit` compares every
`verified` row against real git objects and exits 1 on any claim without one.

If a phase is genuinely blocked:
```bash
venv/bin/python3.12 scripts/campaign.py --slug <slug> block <n> "why"
```

## 4. Non-negotiables

- Ledger updates are committed **immediately after each phase**, never batched
  at the end. That is the entire point — a batched ledger is lost on a crash.
- No phase reaches `verified` without both a passing command and a commit.
- Report to Jacob only at campaign completion, at a real blocker, or when he
  asks. No per-phase status pings.

## 5. Before the session ends

The moment you sense a limit approaching, stop starting new work and run:

```bash
venv/bin/python3.12 scripts/campaign.py --slug <slug> handoff
```

That writes and commits the HANDOFF section: open branches, worktrees, running
processes, and the single next action. Then run the `session-end` skill for
`.claude/STATE.md` / `.claude/HANDOFF.md`, which remain the session-continuity
authority — the campaign ledger is phase state for one task, not a second
backlog and not a roadmap.
