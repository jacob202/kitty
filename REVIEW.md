# Review guidance for Kitty

Instructions for automated review of this repository. Every rule below traces to
a failure that happened here, not to taste.

## What this repository is

Kitty is a local-first, single-user AI companion on one person's Mac: a FastAPI
gateway, a Next.js UI, a local model proxy, and KittyBuilder — an autonomous
worker that executes bounded packets of work unattended, on a budget, in
sandboxed git worktrees.

Two consequences shape every review here.

**Most changes are made by agents and reviewed by agents.** Wrong-but-plausible
code is the expensive failure mode, not ugly code.

**The owner does not program.** A finding he cannot act on is a finding that
costs him time. Name what breaks and what it means, not the class or function
that holds it.

## What counts as a defect here

The usual correctness, security, data-integrity and regression risks, plus these
classes, all of which have shipped and cost real time:

**A gate that can pass without proving anything.** `pytest.ini` deselects
integration-marked tests by default, so a validation command naming a file whose
tests are all integration-marked collects nothing and exits 0. It reports green
having run nothing. Flag any check that can succeed while selecting zero tests,
and any command whose success does not depend on the change it guards.

**Configuration naming something nothing provides.** A route named a model that
no provider block registered, so an autonomous worker was switched on and
executed nothing for a day — silently, because the request was rejected before
billing and the spend ledger stayed quiet. Flag a config value that names a
model, dependency, path or capability with nothing on the other side.

**A message that is true and unusable.** A blocked mutation reported "session X
has no active claim", where X was a dead id read from a stale file; the reader
went hunting for a released lease instead of claiming a new one. A crashed
subprocess surfaced as a JSON decoding error because stderr was discarded. Flag
an error, refusal or status that states a fact without naming the cause or the
next move.

**A test that disagrees with its own change.** Assertions that contradict the
code in the same commit, or two tests in one change that contradict each other.

**A claim of completion not backed by what ran.** Passing tests are evidence, not
proof of runtime or product acceptance. Flag a summary asserting an outcome that
the recorded commands do not demonstrate.

## If you propose or commit a fix

This is the rule that matters most, and the one most recently broken.

**A partial fix is worse than a reported finding.** Anything you change must
leave the repository valid on its own:

- data and config files must still parse;
- tests must agree with the code they cover in the same change;
- no truncated, duplicated or half-applied edit may be left behind;
- if you rename or change a behaviour, update every assertion that pins it.

Two recent examples of getting this wrong. A change correctly made a preflight
check non-destructive but left the test still demanding an error message the new
code no longer produced, so the branch went red. Another correctly retired a
merged pull request's state but left a trailing comma in both JSON blocks, so
neither file parsed, and duplicated a section whose first line was cut off
mid-word.

Both had sound reasoning and broken execution. If you cannot complete a fix
safely, report the finding and stop.

## What not to report

- Naming, formatting, and generic best-practice preferences.
- Speculative refactors, or architecture the change does not touch.
- Process, approval or ownership policy, unless the changed code crosses a
  concrete enforcement boundary in this repository.
- Anything you cannot tie to the changed code and current repository evidence.

Distinguish confirmed defects from plausible concerns, and say which is which.

## How much effort to spend

Scale to blast radius, not to diff size. A one-line change to a gate deserves
more scrutiny than a hundred lines of documentation.

**Most:** anything that can corrupt durable state, spend money, publish or merge,
change what the pipeline trusts, or block other lanes — publication and review
gates, coordination claims, budget and model routing, continuity records, auth,
secrets, and the Builder execution boundary.

**Least:** documentation, comments, and test-only changes that touch no product
behaviour.

## Enforcement boundaries specific to Kitty

- **Publication is gated.** Builder may not push, open pull requests, or merge
  outside its approved packet path. Never infer human approval from a bot
  identity.
- **Spend is capped** at CAD 6.00 per week by the compute governor. Free routes
  are the default and the free lane rejects a paid model override outright. Flag
  any change that widens spend, bypasses the governor, or raises a ceiling.
- **Packets are contracts.** `docs/packets/PACKET_STANDARD.md` governs them. A
  packet whose `allowed_paths` cannot hold a file it must create is a
  non-repairable scope violation, and its attempt is lost.
- **Continuity files** (`.claude/STATE.md`, `.claude/HANDOFF.md`) are shared
  compatibility records that several lanes read. Changes to them must keep both
  files parseable and consistent with each other.
- **Worktrees are normal here.** Tooling that assumes the canonical checkout —
  a virtualenv, `node_modules`, a data root — is broken for every agent, because
  agents work in worktrees almost exclusively.
