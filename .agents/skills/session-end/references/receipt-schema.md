# KB Effectiveness Receipt — Schema

Create one JSON payload and record it with:

```bash
python3 scripts/kb_effectiveness.py record --payload-json '<json>'
```

## Full field set

```json
{
  "schema_version": 1,
  "session_id": "<stable session or attempt identity>",
  "recorded_at": "<ISO timestamp with timezone>",
  "execution_owner": "interactive | builder",
  "tool": "<claude-code | opencode | codex | builder-worker | other>",
  "task_class": "<planning | investigation | code_change | review | recovery | other>",
  "outcome": "accepted | completed_unreviewed | blocked | failed | cancelled | no_op",
  "kb_entries_consulted": [],
  "kb_entries_used": [],
  "kb_entries_stale_or_wrong": [],
  "promoted_to_canonical": [],
  "kb_tokens_loaded": null,
  "total_tokens": null,
  "estimated_cost_usd": null,
  "elapsed_seconds": null,
  "attempts": null,
  "repair_commits": null,
  "regressions": null,
  "first_pass_approved": null,
  "duplicate_work_avoided": null,
  "correction_prevented": null,
  "result_id": null,
  "task_id": null,
  "initiative_id": null,
  "packet_id": null,
  "branch": null,
  "head_sha": null,
  "notes": null
}
```

## Field rules

- Never estimate tokens, elapsed time, cost, attempts, review, or regressions
  from intuition. Use `null` when the source is unavailable.
- `schema_version`, `recorded_at`, and `result_id` are required for `accepted`;
  an accepted result ID may occur in only one accepted receipt, so an interactive
  review cannot double-count a Builder implementation.
- `accepted` requires the passing formal completion review (SKILL.md step 3A)
  plus independent acceptance evidence, not self-declaration.
- `kb_entries_used` and `kb_entries_stale_or_wrong` must be subsets of consulted
  entries and may not overlap.
- `duplicate_work_avoided` or `correction_prevented` is true only when there is a
  concrete avoided action/failure to name in `notes`.
- A Builder worker uses Builder's task/attempt/run identity for `session_id`.
- An interactive tool uses its durable session identifier when available;
  otherwise use a stable repository/branch/timestamp identity and do not reuse
  it for a different receipt.
- The recorder is idempotent for identical receipts, rejects a conflicting
  receipt for the same session ID, and hash-chains retained history. That chain
  detects altered or reordered retained entries; the local file is not an
  immutable audit system, so externally retain/export a head when that assurance
  matters.
- Storage is `~/kb/metrics/kb-effectiveness.jsonl`; when KB is unavailable the
  staged fallback is `docs/session-notes/kb-effectiveness.jsonl`.
- Corrupt history, unknown keys, and fabricated zeroes fail loudly.

## Summary generation

```bash
python3 scripts/kb_effectiveness.py summary --window-days 30
# human-readable:
python3 scripts/kb_effectiveness.py summary --window-days 30 --report
```

The report tracks retrieval usefulness/staleness, known token/cost coverage,
attempts, first-pass approval, regressions, duplicate work avoided, corrections
prevented, canonical-promotion coverage, and KB-used versus no-KB cohorts. Raw
entry and promotion counts are audit coverage, not a score for verbosity. Cohort
comparison is observational and never proves causation.

Do not claim that the KB saves tokens or improves code until the report has
sufficient accepted results, complete enough measurements, and an independently
reviewed comparison. Report all evidence gaps.
