# KH-BUILDER-SEC-02 — New Builder validation commands execute without a shell

**Initiative:** `kitty-hardening-builder-validation-argv-20260903-v1`
**Owner:** Builder after explicit operator activation
**Default route:** free; no `policy.routing` pin
**Base authored against:** `origin/main` `70c15583a6afa4aac9a6f6eb11abf840afa377a4`
**Status:** authored only — not applied, queued, or dispatched

## What Jacob can do after this
Jacob can author new Builder packets knowing validation cannot execute shell metacharacters or arbitrary command composition.

## Verified finding
`run_validation` and `builder_contract._run_command` execute manifest strings with `shell=True`; comments already name the unfinished hardening plan. Historical/new manifests also contain shell composition and, in some recent cases, Node commands that conflict with the active packet standard.

## Objective
Depend on KH-BUILDER-SEC-01 and do not activate until current ONE KITTY execution is complete. Introduce one safe validation-command grammar for new/apply-time packets: tokenize supported command strings with `shlex`, reject shell control/redirection/substitution constructs, and execute argv with `shell=False`. Make `scripts/packet_preflight.py`, contract validation, initiative apply, and runtime execution agree on the same grammar. Before enforcement, inventory currently queued/nonterminal Builder packets and committed active manifests for commands that would become invalid; record the list in evidence and migrate only committed packet manifests that are current authorities, never rewrite historical `data/` receipts. Already-applied unsafe queue rows must fail closed with `needs_decision`/clear operator guidance rather than silently execute through a compatibility shell. Preserve the packet-standard supported forms (`python -m pytest ...`, `python -m ruff check ...`).

## Intended files / fence
- `gateway/`
- `scripts/`
- `docs/packets/`
- `tests/`

Directory entries are deliberate because this packet may create the specifically named helper/migration/test described in the objective. The worker must still stay inside the narrow objective; a directory fence is not permission for opportunistic refactoring.

## Acceptance criteria
1. Newly validated/applied packet commands containing pipes, semicolons, ampersands, redirection, command substitution, or backticks are rejected before a task attempt.
2. Supported Python pytest/ruff commands run as argv with shell=False and preserve quoted path/keyword arguments correctly.
3. Preflight, manifest validation/apply, contract runner, and attempt validation use one command parser/policy rather than four divergent checks.
4. Nonterminal legacy queue rows that cannot satisfy the safe grammar are surfaced for operator decision and are never silently executed with shell=True.
5. Historical receipts/manifests under data remain immutable evidence.
6. The packet evidence contains a pre-enforcement compatibility inventory so rollout cannot strand unknown active work.

## Verification
**Tier 1 — Builder mechanical.** These are the only commands Builder runs:
- `python -m pytest -q tests/test_builder_attempt.py tests/test_builder_contract.py tests/test_builder_initiative.py tests/test_packet_preflight.py`
- `python -m ruff check gateway/builder_attempt.py gateway/builder_contract.py gateway/builder_initiative.py gateway/builder_validation_command.py scripts/packet_preflight.py tests/test_builder_attempt.py tests/test_builder_contract.py tests/test_builder_initiative.py tests/test_packet_preflight.py`

**Tier 2 / Tier 3.** Tier 2: dry-run compatibility inventory plus subprocess tests proving shell metacharacters are inert/rejected. No product UI PA. Independent security review required before merge.

Current-green tests are baseline only. The implementation must add or strengthen at least one regression that fails on `70c15583a6afa4aac9a6f6eb11abf840afa377a4` for the verified finding before production edits.

## Failure modes that must be tested
- The original review reproduction is a required RED case, not prose-only evidence.
- Dependency/service unavailable paths stay truthful; UNKNOWN never becomes success.
- Cancellation/timeout/partial input cannot leave a false success receipt.
- The fix must preserve the existing security/authority boundary named in the objective.

## Stop condition
If current nonterminal work depends on a shell feature and no equivalent safe argv command exists, stop and park that task for explicit operator migration; do not add a hidden legacy-shell fallback.

## Recovery / restartability
No destructive queue migration. Enforcement is at author/apply/run gates; incompatible rows remain durable and inspectable.

## Dedupe / ownership guard
Before activation, re-read `workspace_global`, GitHub issue #490, current Git/PR state, and Builder task ownership. If current `main` already contains an equivalent fix or another live lane owns any implementation path, stop and reconcile rather than creating competing work. This packet never authorizes push, PR creation, merge, paid spend, credential mutation, or edits under `data/`.
