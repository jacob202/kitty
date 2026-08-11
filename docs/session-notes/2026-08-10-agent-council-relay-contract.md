# Outcome contract: local agent council relay

## User-visible outcome

From the existing Discord `#general` conversation, Jacob can write `council: <question>` and have Kitty obtain independent read-only opinions from local Codex, Claude, and OpenCode CLI workers without Jacob copying the prompt between agents. If the direct Claude worker fails, the relay must report that failure explicitly and may make one visible fallback attempt.

## Acceptance criteria

1. `python3 scripts/agent_council.py --help` documents the relay interface.
2. The relay launches configured workers without a shell, gives each a read-only instruction, enforces read-only worker permissions, and returns a labeled result for every worker, including explicit failures and any visible fallback attempt.
3. Worker execution is bounded by a timeout and does not grant write, approval-bypass, or destructive permissions.
4. The project skill tells the persistent Kitty/Letta agent exactly when and how to invoke the relay, including the no-op path for ordinary messages.
5. Focused tests cover command construction, worker failure reporting, and output labeling without making live model calls.

## Verification

```bash
python3 scripts/agent_council.py --help
python3 -m pytest -q tests/test_agent_council.py
python3 scripts/agent_council.py --dry-run "test council wiring"
```

## Non-goals and prohibited shortcuts

- Do not change Discord bot permissions or enable bot-to-bot message ingestion.
- Do not read or print credentials.
- Do not let council workers edit files, publish changes, send external messages, or spend money.
- Do not make ordinary Discord messages invoke the council automatically.

## Evidence artifacts

- `scripts/agent_council.py`
- `.skills/agent-council/SKILL.md`
- `tests/test_agent_council.py`
- Focused command output recorded in the final handoff.

## Repair limit

Two focused repair cycles; stop and report the exact failing criterion after that.
