# Vibe Coder Workflow (Session-First)

Use this when you want fast momentum without losing quality or scope control.

## Session loop

1. Define one outcome for this session.
2. Timebox to 45–90 minutes.
3. End with a clean handoff note.

Generate a ready-to-fill session scaffold:

```bash
make vibe-session OUTCOME="one clear result" MINUTES=60
```

Or run the script directly:

```bash
python3.12 /home/runner/work/kitty/kitty/scripts/vibe_session.py "one clear result" --minutes 60 --active-task "one active task"
```

The scaffold is written to:

`/home/runner/work/kitty/kitty/.agent/session_logs/<timestamp>-vibe-session.md`

## Strict task funnel

- Capture interruptions/ideas quickly.
- Keep exactly one active task.
- Move everything else to backlog or parking lot.

## Start checklist for every coding task

- Repo state check (`git status --short --branch`)
- One-sentence scope definition
- Explicit done criteria:
  - tests
  - checks
  - docs

## Tight implementation discipline

- Smallest possible diff
- One concern per commit
- Run narrowest relevant tests first

## PR quality standard

- Clear, scoped title
- User impact summary
- Exact verification commands + pass/fail results
- Explicit note on intentionally skipped work

## Anti-chaos guardrails

- No context switching mid-session
- No “just one more” scope expansion
- Interruptions go to parking lot, not into current diff

## Weekly workflow review (15 minutes)

- What caused friction this week?
- What repeated and should become a rule?
- What can be automated next week?
