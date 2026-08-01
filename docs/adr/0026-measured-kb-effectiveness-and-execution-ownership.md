# ADR 0026: Measured KB Effectiveness and Single Execution Ownership

- **Status:** Accepted
- **Date:** 2026-08-01
- **Decision owner:** Jacob
- **Relates to:** ADR 0017, ADR 0021, ADR 0023, ADR 0025

## Context

The cross-tool knowledge base can preserve continuity, corrections, model
quirks, and verified findings. That is useful, but writing more knowledge is not
proof that the system learns. The project did not record which KB entries were
consulted, which influenced the work, which were stale, how much context they
added, or whether the resulting work required fewer attempts, passed review on
the first try, avoided duplicate work, or produced fewer regressions.

Kitty already has partial telemetry:

- model/provider token ledgers and cost summaries;
- Builder attempts, validation, review, and campaign reports;
- session-end continuity and workflow signals.

These sources were not joined by a per-session evidence receipt, so claims such
as "the KB saves tokens" or "the KB improves code" were not testable.

At the same time, the implementation of a cross-tool bare `next` command briefly
made interactive tools select Builder packets. That exposed a deeper
measurement problem: outcomes cannot be compared or attributed when the same
implementation appears to be owned by both an interactive session and Builder.

## Decision

### One execution owner

Every implementation records exactly one execution owner:

```text
interactive | builder
```

`builder` requires a valid Builder task/packet bundle or explicit durable
ownership transfer with matching live lease. A manually opened Claude Code,
OpenCode, Codex, or other tool is `interactive` by default. Reviewing Builder
output does not transfer implementation ownership.

### Append-only effectiveness receipts

The canonical recorder and reporter is:

```text
scripts/kb_effectiveness.py
```

Normal storage is:

```text
~/kb/metrics/kb-effectiveness.jsonl
```

When `~/kb` is unavailable, a complete staged fallback may be written to:

```text
docs/session-notes/kb-effectiveness.jsonl
```

The fallback is a transfer artifact, not a second long-term store.

Each receipt records:

- stable session/attempt identity;
- execution owner and tool;
- task class and verified outcome;
- KB entries consulted, used, and stale/wrong;
- canonical artifacts promoted from KB knowledge;
- known KB context tokens, total tokens, cost, elapsed time, attempts, repair
  commits, regressions, and first-pass independent approval;
- concrete duplicate work or correction prevented;
- Builder/task/packet, branch, HEAD, and result references when applicable.

Unknown measurements are `null`. They are never inferred from prose or replaced
with zero.

### Strict identity and history

- Identical receipts are idempotent.
- The same session ID with different content is a conflict and fails.
- `schema_version`, timestamp, and an accepted result ID are required; accepted
  result IDs are unique so Builder and interactive records cannot double-count
  one implementation.
- Each JSONL entry carries the preceding entry's hash and its own deterministic
  chain hash. Reordering or changing retained history fails loudly. The local
  ledger is tamper-evident, not immutable: truncating its final tail still needs
  a separately retained/exported head to detect.
- Unknown fields, invalid subset relationships, malformed SHAs, corrupt JSONL,
  blank history lines, receipt-ID mismatches, and chain mismatches fail loudly.
- Useful and stale/wrong entry sets are disjoint and both are subsets of
  consulted entries.
- `accepted` requires independent acceptance evidence. Self-tested or
  completed-but-unreviewed work uses `completed_unreviewed`.

### Reports and interpretation

The rolling report includes:

- receipt and evidence coverage;
- retrieval usefulness and stale/wrong rates;
- known token, context-token, and cost totals (or `null` when no measurement is
  known);
- attempts and repair commits;
- first-pass review approval and regressions;
- duplicate work and corrections prevented;
- canonical-promotion coverage per session/result, rather than a raw count that
  rewards verbose artifact lists;
- KB-used versus no-KB cohorts.

The cohort comparison is observational. It does not prove causation. The system
must not claim token savings, quality improvement, or time savings when sample
sizes are small, measurements are incomplete, acceptance is self-declared, or
cohorts differ materially by task class/tool/model.

The primary optimization target is:

> lower total cost and time per independently accepted outcome, without more
> regressions or hidden duplicate work.

Raw token reduction alone is not success.
Entry and promotion counts are audit coverage, never a success score.

### No new authority

The effectiveness ledger is measurement only. It does not:

- create or prioritize roadmap work;
- apply initiatives;
- claim or schedule Builder packets;
- open issues;
- mutate continuity state;
- promote workflow signals into execution.

Session-end writes one receipt after reconciling evidence. Builder attempts may
write receipts using their own durable task/attempt identity, but Builder
remains the execution authority.

## Consequences

- The project can distinguish knowledge capture from demonstrated improvement.
- Missing telemetry becomes visible instead of silently flattering the system.
- Interactive and Builder outcomes can be compared without double-counting one
  implementation.
- Stale KB entries become measurable and removable.
- Proven knowledge can graduate into canonical enforcement rather than living
  forever as optional prose.
- Historical sessions without receipts remain unmeasured; no retroactive claims
  are allowed.
- Early reports will mostly expose evidence gaps. That is an expected and useful
  result.

## Acceptance

This decision is implemented when:

- a valid receipt is hash-chained, tamper-evident, and idempotent;
- a conflicting session receipt fails;
- unknown fields and corrupt history fail loudly;
- used/stale entry relationships are validated;
- unknown token/quality fields remain unknown in the summary rather than zero;
- retrieval, efficiency, quality, and cohort metrics are computed from fixtures;
- the report explicitly states that cohort comparison is not causal;
- session-end records one execution owner and one effectiveness receipt; and
- bare interactive `next` cannot consume Builder work.

## Revisit triggers

Revisit when:

- receipts are routinely skipped or fabricated;
- task classes/tools/models make cohort comparison misleading;
- token telemetry can be joined automatically by stable session/run identity;
- the fallback store accumulates instead of transferring to `~/kb`;
- measurement overhead materially increases session cost;
- privacy-sensitive KB paths or notes appear in exported reports; or
- a statistically defensible experiment design is needed to establish causal
  impact.
