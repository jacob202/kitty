# KH-GATE-01 — a gate that cannot run must say what would fix it

**Initiative:** kitty-hardening-v1
**Owner:** builder
**Depends on:** none
**Free or paid:** free

## What Jacob can do after this

Get told the one command that unblocks a push, instead of being told a check
could not run reliably and left to work out why.

## Why this is the next thing

On 2026-09-16 a push carrying two frontend files was refused with:

```
Push blocked by publication infrastructure. 2 gate(s) could not run reliably: web tests web build
```

The cause is that `scripts/hooks/pre-push` runs
`./node_modules/.bin/vitest` and `node node_modules/next/dist/bin/next build`
from the pushing checkout, and a git worktree has no `node_modules` — the
directory is gitignored and exists only in the checkout that owns the repository.
One `npm ci` in `gateway/kitty-chat` cleared it completely.

The gate's behaviour is right and is not what this packet changes. It refused to
report a pass it had not proven, which is the single piece of tooling that
behaved well across that entire session. What it did not do is say that the
dependencies were missing, or that installing them was the fix. The previous lane
to hit this reached for `--no-verify`, and an earlier one tried symlinking
`node_modules` from the canonical checkout, which broke a Next build and had to
be replaced with a real install.

Both of those are what a person does when a blocker gives them no next step.

## Plan

1. Detect the specific case: the gate's executable is absent because
   `node_modules` is not there, as distinct from the gate running and failing.
2. Report the exact command and directory — `cd gateway/kitty-chat && npm ci` —
   in the blocking message.
3. Keep blocking. An unrunnable check is never a passing one, and nothing here
   should make it easier to push without proof.
4. Keep a genuine test failure reported as a failure. The two must not blur: one
   means the environment is incomplete, the other means the code is wrong, and
   conflating them would teach people to run `npm ci` at real regressions.
5. Do not skip, downgrade, or auto-install anything. A hook that installs 574 MB
   of dependencies on someone's behalf during a push is a surprise, not a
   convenience.

## Not in scope

Making frontend gates runnable from a worktree without an install — resolving a
canonical `node_modules` across checkouts is real work with a known failed
attempt behind it, and it belongs with the Builder toolchain packets in
`builder-frontend-proof-v1`. Changing which gates run, their commands, or the
conditions under which frontend gates are triggered.

## Verification

**Tier 1 — mechanical.**

```
python -m pytest -q -m "integration or not integration" tests/test_pre_push_gate.py
```

Today this collects 26 tests and passes; they assert the hook's contents against
the CI workflow, including that the web build never writes the live `.next`
directory. The new cases must assert the actionable message appears when the
dependency is absent and does *not* appear for a gate that ran and failed —
without that second assertion, an implementation that prints the install hint on
every frontend failure would pass.

**Tier 2 — running app.** Not applicable.

**Tier 3 — product acceptance.** Not applicable.

## Stop condition

Stop and escalate if a missing dependency cannot be distinguished from a failing
test with what the hook can observe. Printing the install command on every
frontend failure would be worse than printing it never: it would send someone to
reinstall dependencies while staring at a real regression.

## Recovery

The hook is a shell script and the change is to its reporting. Revert
`scripts/hooks/pre-push` to `HEAD` and re-run. Because nothing about which gates
run or how they are evaluated changes, a failed attempt cannot let an unproven
push through — the worst case is the same unhelpful message as today.
