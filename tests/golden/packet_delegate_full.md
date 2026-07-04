# Packet 15 — Fix the frobnicator

- **Status:** draft (generated 2026-07-04 from action 42)
- **Best executor:** Claude Code
- **Purpose:** Make frobnication reliable.

## Exact scope

- Update frob()
- Add tests

## Files likely touched

- gateway/frob.py
- tests/test_frob.py

## Files not to touch

- gateway/ui.py

## Steps

1. Reproduce
2. Fix
3. Test

## Acceptance criteria

- Tests pass

## Verification

```bash
pytest tests/test_frob.py
```

## Risks / rollback

- Breaking change

## Too broad if

It refactors the whole module.

## Jacob reviews

- The API change
