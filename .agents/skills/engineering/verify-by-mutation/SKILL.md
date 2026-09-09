---
name: verify-by-mutation
description: Prove a test actually catches the defect it claims to guard, by mutating the code under test and confirming the test fails. Use when the user wants to verify a test is real, harden a test suite, check that a smoke assertion isn't vacuous, prove a regression test would catch a regression, or audit test quality. Grounded in Kitty's standard: a spec that passes vacuously is a fake pass, and mutation-testing is the bar for smoke assertions. The verification sibling of improve-codebase-architecture, harden-codebase, and improve-daily-ux — those propose changes; this one proves the tests guarding them are real.
---

# Verify By Mutation

Prove a test is **real** — that it actually fails when the behaviour it guards is
broken. A test that passes whether or not the code is correct is a **vacuous pass**:
it looks like coverage and guards nothing. The aim is to turn "the test passes" into
"the test fails when it should, for the right reason." This is the verification
sibling of the other three skills: they propose changes; this one proves the tests
guarding those changes are load-bearing.

> **Kitty's standard (load-bearing):** a spec that passes vacuously is a fake pass.
> Mutation-testing is the bar for smoke assertions. Never report a test as passing
> without evidence it can fail.

## Glossary

Use these terms exactly. Consistent language is the point — don't drift into "test
coverage," "test quality," or "edge cases." The canonical definitions live in
[LANGUAGE.md](LANGUAGE.md), injected below; the "Key principles" summary follows.

!`cat "${COMMANDCODE_SKILL_DIR}/LANGUAGE.md"`

Key principles (see LANGUAGE.md for full definitions):

- **The mutation test**: break the code under test on purpose, run the test, confirm
  it FAILS. If it still passes, the test is vacuous — it never touched the behaviour.
- **A green suite proves nothing on its own.** Green means "no test failed," not "the
  behaviour is guarded." Only a mutation that turns a test red proves the guard exists.
- **Kill the mutant for the right reason.** A test that fails on a mutation for an
  unrelated reason (a crash, a timeout, a different assertion) is not a real kill.
  Read the failure — it must name the mutated behaviour.
- **One mutation per behaviour.** Don't mutate three things at once; you won't know
  which the test caught.

This skill is _informed_ by the project's testing doctrine. Kitty's `TESTING.md` and
the smoke-assertion standard define what "real" means here; don't re-litigate them.

## Kitty grounding (read first)

Before exploring, read:

| Doc / file | Purpose |
|-----|---------|
| `TESTING.md` | The repo's testing doctrine, commands, and what counts as a real assertion |
| `pytest.ini` / `pyproject.toml` | Test config, markers, coverage thresholds (the pre-push gate requires ≥73%) |
| `gateway/kitty-chat/vitest.config.*` | Frontend test config — the web side has its own runner |
| `tests/` | The Python suite; look for the smoke assertions this skill audits |
| `gateway/kitty-chat/tests/` | The frontend suite (Vitest + Testing Library) |

**Domain vocabulary:** name the actual test and the actual behaviour — e.g. "the
`test_run_workspace` tamper-detection spec," "the `WorkView` group-list scoping
assertion" — not "the test" or "the coverage."

**Recorded decisions:** `docs/adr/` and `docs/DECISIONS.md` are load-bearing. The
mutation-testing standard for smoke assertions is itself a recorded Kitty position —
treat it as doctrine, not a suggestion.

## Failure modes to avoid

- **Trusting green.** A passing suite is not evidence the behaviour is guarded. This
  skill exists precisely because green can be vacuous. Never report "tests pass" as
  proof without a mutation kill.
- **Mutating the test instead of the code.** The mutation goes in the code under test,
  not the assertion. Changing the test to make it fail proves nothing.
- **Accepting a wrong-reason kill.** If the test fails on a mutation but for an
  unrelated reason (import error, timeout, a different assertion firing), that's not
  a kill — it's a coincidence. Read the failure output and confirm it names the
  mutated behaviour.
- **Over-mutating.** Don't mutate unrelated code to "see what happens." Each mutation
  targets one specific behaviour the test claims to guard.
- **Stopping at the first kill.** A test can kill one mutant and miss another. Mutate
  each distinct behaviour the test claims to cover, not just one.
- **Confusing coverage with mutation.** Line/branch coverage says the test *ran* the
  code; mutation says the test *noticed* when the code changed. Coverage is necessary,
  not sufficient.

## Process

<scope_check>
If the user names a specific test or behaviour, skip the Task-tool exploration phase.
Read that test and its code under test directly and move to the mutation loop.
</scope_check>

### 1. Identify the claim

For each test under audit, state what behaviour it claims to guard, in one sentence.
A test whose claim you can't state is already suspect — it may be asserting incident
rather than behaviour. Read the test AND the code under test; the gap between them is
where vacuous passes live.

Use the Task tool (`subagent_type=explore`) to map a large suite only when scope is
large. For a named test, read it directly.

### 2. Mutate and run

For each claimed behaviour:

1. **Introduce a minimal mutation** in the code under test that breaks *that specific
   behaviour* — flip a comparison, swap a return, delete a guard, invert a condition,
   change a constant. One mutation at a time.
2. **Run the test.** Record pass/fail and the failure message.
3. **Verdict:**
   - Test FAILS, and the failure names the mutated behaviour → **real kill.** The
     guard is load-bearing. Revert the mutation.
   - Test PASSES → **vacuous.** The test never touched the behaviour. This is the
     defect. Note it.
   - Test FAILS for an unrelated reason (crash, timeout, different assertion) →
     **wrong-reason kill.** Not real. Note it.
4. **Revert every mutation** before moving on. Never leave mutated code in the tree.

Run the exact command the CI gate runs (`pytest <path> -q` for Python,
`vitest run <path>` for frontend) so the verdict matches what the gate sees.

### 3. Report and fix

Present a numbered list of findings. For each:

- **Test** — the named test and the behaviour it claims to guard
- **Mutation** — the exact change you introduced
- **Verdict** — real kill / vacuous / wrong-reason kill, with the failure message
- **Fix** — for a vacuous or wrong-reason test, the assertion that would actually
  catch the mutation

Then, with the user's go-ahead, fix the vacuous tests: add or tighten the assertion
so the mutation now produces a real kill. Re-run the mutation to confirm the fix
works — a fix isn't done until the previously-vacuous test now fails on the mutation
and passes on correct code.

### 4. Cross-layer handoffs

- **A vacuous test guarding a runtime failure path?** That's `harden-codebase`
  territory — the failure path may be quiet *and* unguarded.
- **A vacuous test guarding a user-facing state?** That's `improve-daily-ux` — the
  surface may show the wrong state *and* nothing catches it.
- **A test that can't be mutated cleanly because the code is untestable through its
  interface?** That's `improve-codebase-architecture` — the module shape is blocking
  verification.

Side effects happen inline as decisions crystallize:

- **A mutation reveals a behaviour nobody documented?** Add a short definition to
  `docs/ARCHITECTURE.md` or a new `docs/CONTEXT.md` using
  [CONTEXT-FORMAT.md](../improve-codebase-architecture/CONTEXT-FORMAT.md) (shared).
- **User rejects a finding with a load-bearing reason?** Offer an ADR at
  `docs/adr/NNNN-title.md` so future verification audits don't re-suggest it. See
  [ADR-FORMAT.md](../improve-codebase-architecture/ADR-FORMAT.md) (shared).
