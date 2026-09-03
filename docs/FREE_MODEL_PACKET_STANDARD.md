# Free-Model Packet Standard

**Status:** ratified 2026-07-26. Phase 1 artifact under `docs/ALIGNMENT_MAP.md`.

This is a packet-quality and classification contract, not a routing or budget
status report. Current route, provider, model, and cost truth lives in
`docs/FREE_WORKERS.md` and the Builder configuration it points to
(`config/builder_paid_routes.json`, `config/compute_governor.json`); do not
re-derive either here.

Unattended free execution rests on an engineering assumption, not a claim
about what free models can or cannot do: a `free-exec` packet must not depend
on worker judgment or self-verification, and its correctness must be decidable
by a falsifiable gate — not by the worker's own report. This document defines
what a packet must look like for that to hold, and — more importantly — for
Builder to *prove* it did.

## The one rule

> **A free-model packet moves the thinking out of the worker and into the
> packet and the gate. The model types. The gate decides.**

Every judgement call that would otherwise happen at execution time must
already be resolved in the packet text. Anything left open is a decision the
packet asks the worker to make and then self-report as correct — exactly what
a `free-exec` packet must not require.

## Why this is a verification standard, not a prompting standard

The instinct is "write simpler instructions." That is half of it, and the less
important half.

A worker whose correctness is not independently verified cannot be trusted to
report its own success. So the binding constraint is not *can it do the work* —
it is **can a script tell whether the work is right**. If acceptance requires a
human to look, the packet is not free-model-ready no matter how simple the
instructions are.

This is why the standard is stricter about gates than about wording.

## The gate rules

### G1 — Acceptance must be decidable by exit code

Every packet declares at least one `validation_commands` entry that exits 0
when the work is correct and non-zero when it is not. No packet ships with
acceptance criteria that only a reader can evaluate.

### G2 — The gate must be falsifiable

A gate that would pass even if the work were never done is worse than no gate,
because it manufactures false evidence. Before accepting a packet, confirm the
gate **fails on the unmodified tree**.

This is the check that catches the two failure modes already found in this
repo: gates that can never pass (missing target, broken invocation), and gates
that always pass regardless of the diff.

### G3 — The gate must be runnable here

The command must execute on the machine the drain runs on. `npm run <script>`
is banned repo-wide — packet 014 documents it exiting 194 silently. Use the
`make` targets, which are the same path CI uses.

### G4 — New behaviour ships with the test that proves it

If the packet adds behaviour, the packet supplies the test **verbatim** in the
packet body, and `allowed_paths` includes the test file. The worker copies it
in; it does not invent it. A free model writing its own acceptance test will
write one that passes.

## The packet rules

### P1 — No discovery

Name the exact file, the exact function, and the exact anchor text to change.
Never "find where X is handled." If the worker has to search, it will pick
wrong and be confident about it.

### P2 — No design choices

Names, signatures, file locations, error messages, and data shapes are decided
in the packet. Anything phrased as "appropriately", "as needed", "consistent
with", or "sensible" is a decision that has not been made yet.

### P3 — One outcome, smallest possible blast radius

One packet, one behaviour change. Prefer one file. `allowed_paths` is the tight
set, never a directory when a file will do.

### P4 — Closed world

The packet must not require changes to callers, imports, or config it does not
name. "And update any callers" is a reasoning task. If callers must change,
either name every one of them explicitly or split the packet.

### P5 — Literal before/after where possible

For edits to existing code, quote the exact current text and the exact
replacement. The best free-model packet is closer to a patch with prose around
it than to a specification.

### P6 — Honest failure beats partial success

Keep the shell adapter's earned rule: a worker may hand off only on clean
failure, and any partial work fails the attempt with the worktree preserved.
Never write a packet that invites a worker to do "as much as it can."

## Disqualifiers

A packet is **not** free-model-ready if it requires any of:

- reading the codebase to decide what to change
- choosing between two valid implementations
- refactoring, renaming across files, or "cleaning up while you're in there"
- judgement about UX, copy, visual design, or product behaviour
- changing dependencies, lockfiles, CI workflows, or auth/secrets
- multi-file coordinated change without every file named
- acceptance that a human has to eyeball (screenshots, "looks right", tone)

These are not lesser packets. They are **paid-model packets** — authored or
executed with a strong model, deliberately, in daylight. The point of the split
is that they are a small minority.

## Packet classes

Every packet carries one of these, replacing the old `Best executor` line.

| Class | Meaning | Runs where |
|---|---|---|
| `free-exec` | Meets every rule above | nightly drain, unattended |
| `free-exec-blocked` | Would qualify, but its gate can't run yet | nightly drain, once CI is green |
| `paid-author` | Free model can execute it *after* a strong model writes the patch-level detail | drain, after authoring |
| `paid-exec` | Needs judgement at execution time | interactive session only |
| `human` | Needs Jacob (accounts, money, decisions, physical world) | not Builder work at all |
| `idea` | Not a packet yet — a thought worth keeping | nowhere; parked |

`paid-author` is the important one. Most existing packets land here: the *idea*
is sound and the work is mechanical, but nobody has yet written down the exact
edits. Converting `paid-author` → `free-exec` is the highest-leverage use of
paid tokens available, because each conversion permanently moves work onto the
free train.

## Authoring checklist

Before a packet is marked `free-exec`:

- [ ] Exactly one outcome
- [ ] Every file named; `allowed_paths` is the tight set
- [ ] Every decision resolved in the text — no "appropriate", "as needed"
- [ ] Exact anchor text quoted for each edit
- [ ] At least one `validation_commands` entry that exits non-zero on a wrong tree
- [ ] Gate verified to **fail** on the unmodified tree (G2)
- [ ] Gate verified to **run** on this machine (G3)
- [ ] Any new test supplied verbatim and covered by `allowed_paths`
- [ ] No dependency, lockfile, CI, or secret changes
- [ ] Stopping rule: what the worker does when it cannot proceed cleanly

## Worked shape

```
Objective
  In gateway/builder_initiative.py, replace the body of _path_or_glob_exists
  with the text in "After" below. Change nothing else in the file.

Before (exact current text)
  <quoted verbatim>

After (exact replacement)
  <quoted verbatim>

allowed_paths
  gateway/builder_initiative.py
  tests/test_builder_initiative.py

New test (copy verbatim into tests/test_builder_initiative.py, at the end of
class TestWarnings)
  <full test source>

validation_commands
  python3.12 -m pytest tests/test_builder_initiative.py -q --tb=short

Stopping rule
  If the "Before" text is not found exactly, make no changes and fail the
  attempt. Do not search for something similar.
```

That last line is the difference between a free model that fails honestly and
one that quietly edits the wrong function.
