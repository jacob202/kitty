# Language

Shared vocabulary for every suggestion this skill makes. Use these terms exactly —
don't substitute "test coverage," "test quality," or "edge case." Consistent
language is the whole point.

## Terms

**Claim**
The one behaviour a test says it guards, stated in a sentence. A test whose claim you
can't state is asserting incident, not behaviour.
_Avoid_: purpose, intent (too vague — a claim is falsifiable).

**Mutation**
A minimal, deliberate break in the *code under test* that violates one specific
claim. Flip a comparison, swap a return, delete a guard, invert a condition, change a
constant. One behaviour per mutation.
_Avoid_: change, edit (a mutation is adversarial and targeted, not incidental).

**Mutant**
The code under test with one mutation applied. The thing the test is run against.

**Kill**
A test FAILS on a mutant, and the failure names the mutated behaviour. A kill proves
the guard is load-bearing.
_Avoid_: catch, detect (kill is the standard term and implies a verified failure).

**Real kill**
A kill where the failure message points at the mutated behaviour. The test noticed
*that specific* break.

**Wrong-reason kill** _(defect)_
The test fails on a mutant, but for an unrelated reason — an import error, a timeout,
a different assertion firing. It looks like a kill and isn't. Read the failure to tell
the difference.

**Vacuous pass** _(the defect)_
A test that PASSES on a mutant — the code is broken and the test didn't notice. The
test never touched the behaviour it claims to guard. Kitty's standard: a vacuous pass
is a fake pass.
_Avoid_: false positive (ambiguous about which direction is false).

**Survivor**
A mutant a test fails to kill. A surviving mutant means a vacuous or weak test.

**Code under test**
The production code the test exercises — where the mutation goes. Never the test
file. Mutating the assertion proves nothing.

**Coverage**
Whether the test *ran* a line or branch. Necessary, not sufficient: coverage says the
code executed; a kill says the test *noticed* when it changed.
_Avoid_: using "coverage" to mean "guarded" — they are different things.

**Mutation score**
The fraction of introduced mutants a test (or suite) kills. A proxy for how load-
bearing the assertions are. Not a vanity metric — a low score on a smoke assertion
means the smoke isn't detected.

## Principles

- **The mutation test.** Break the code under test on purpose, run the test, confirm
  it FAILS for the right reason. A test that still passes is vacuous.
- **Green proves nothing on its own.** A passing suite means "no test failed," not
  "the behaviour is guarded." Only a kill is evidence.
- **Kill for the right reason.** A wrong-reason kill is not a kill. The failure must
  name the mutated behaviour — read the output, don't trust the red.
- **One mutation per claim.** Mutate one behaviour at a time or you can't attribute
  the kill.
- **Mutate code, never the test.** The mutation goes in the code under test. Changing
  the assertion to force a failure proves nothing about the guard.
- **Revert every mutant.** Never leave mutated code in the tree. Revert before the
  next mutation and before reporting.
- **A fix isn't done until the mutant dies.** After tightening a vacuous test, re-run
  the mutation: the test must now fail on the mutant and pass on correct code.

## Relationships

- A **Claim** is verified by introducing a **Mutation** to the **code under test**,
  producing a **Mutant**, then running the test.
- The test either **kills** the mutant (real or wrong-reason) or the mutant
  **survives** (a **vacuous pass**).
- **Coverage** says the test ran the code; a **real kill** says the test noticed the
  break. Coverage without kills is unguarded code that looks guarded.
- **Mutation score** aggregates kills across a suite — the load-bearing-ness of the
  assertions, not their count.

## Rejected framings

- **"Coverage" as proof of quality**: a suite can be 100% covered and 0% load-bearing
  if every assertion is vacuous. We use mutation score, not line coverage, as the
  bar.
- **"The test passes, so it works"**: the exact belief this skill exists to falsify.
  A pass on correct code is necessary; a fail on a mutant is what proves the guard.
- **"More tests = better"**: count is not the metric. One real kill beats ten
  vacuous passes.
- **Mutating the test to make it fail**: that's rigging, not verification. The mutant
  always goes in the code under test.
