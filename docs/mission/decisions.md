# Decisions — binding, cross-cutting

Each decision states what it settles and what would reverse it. A later
session may overturn any of these, but must say so explicitly and record why.

## D1 — Green main precedes everything

Nothing downstream is verifiable while `pip install -r requirements.txt`
fails. Outcomes A, B and C all rest on a suite that can run. The dependency
repair is therefore slice 0, ahead of all image and Builder work.

Reverses if: main is green by another route and the repair is redundant.

## D2 — Fix the pin, not the library

`openai` restored to `>=1.90.0,<1.110.0` (mem0ai 0.1.x's own ceiling) rather
than bumping `mem0ai` 0.1.118 → 2.0.14.

mem0ai 2.0.x drops the openai upper bound entirely and is the better long-term
answer, but it is a major-version API break against `gateway/memory.py` and
`gateway/doctor.py` and cannot be verified without a live memory backend. That
is a separate slice with its own evidence, not a side effect of a CI repair.

Direct `openai` SDK use is only `from openai import OpenAI` in
`mcp/imagen/engines/dalle.py:22` and `mcp/imagen/server.py:104` — a
constructor stable across 1.x and 2.x — so the downgrade breaks no caller.
Everything else reaches OpenAI-compatible endpoints over httpx.

Reverses if: mem0ai 2.x is verified against a live backend.

## D3 — Issue #336 outranks the roadmap's Phase 3 gate

`docs/ROADMAP.md` §3.4 lists the RunPod/Image Studio lane as
`BLOCKED (awaiting Phase 3 authorization)`, behind Phase 1 and Phase 2, all
`PENDING`. Issue #336 (2026-08-01) declares the conversational Image Agent an
"active, Jacob-authorized product slice as of 2026-07-31" and the mission
brief names it priority 1.

Jacob authorized it. The gate is satisfied, not bypassed. The roadmap is the
stale document here, and Outcome C corrects it.

Reverses if: Jacob withdraws the authorization.

## D4 — The image slice is sequenced local-testable first

Issue #336's acceptance test is a browser + GPU flow. Its stop rule says the
first PR succeeds only when that flow is real. That does not mean the work is
indivisible: the ordering below puts everything with local test evidence
before anything needing a GPU, so a credentialed session spends its GPU budget
on the parts that actually require one.

A1–A3 are unit-testable anywhere. A4–A5 need Kitty running. A6 needs RunPod.
No slice may claim VERIFIED on unit tests alone when its outcome is user-visible.

Reverses if: a session with full credentials wants to drive the whole slice at
once — the ordering is an optimisation, not a constraint.

## D5 — Builder is inventoried before it is changed

27 `builder_*` modules exist. Which is the live execution path is unknown.
Outcome B item 1 ("reconstruct the actual Builder architecture") is a
prerequisite for items 2–10, and no Builder code changes this session.

Guessing at "the dead entry point" without runtime evidence is how duplicate
launchers get created — which is the exact failure Outcome B exists to fix.

Reverses if: nothing. Inventory first is unconditional.

## D6 — Conversational KittyBuilder is deferred, not dropped

Jacob's note that "kittybuilder is also supposed to be conversational" is
recorded as a real product requirement. It is not in Outcome B's ten items and
does not block them. It lands after Builder state is deterministic and
observable — a conversational surface over non-deterministic state would
narrate a lie fluently.

Reverses if: Jacob reprioritises it above Builder determinism.

## D7 — Evidence is produced, never asserted

No status in this mission's files may be raised on the strength of a document,
a prior session's claim, or a passing unit test standing in for a user-visible
outcome. `IMPLEMENTED-NOT-VERIFIED` is the honest resting state for work whose
real check needs hardware this session lacks, and is preferred over a VERIFIED
that a reader cannot reproduce.

The roadmap claiming a green main that had been red for 8 commits is the
precise failure this rule exists to prevent.

Reverses if: nothing.
