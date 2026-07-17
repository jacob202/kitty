# Active Mission — Project Control Plane / Continuity Foundation

<!-- kitty-mission
{
  "schema_version": 1,
  "mission_id": "PCPF-001",
  "status": "running",
  "approved_at": "2026-07-17T00:00:00Z",
  "approved_by": "Jacob",
  "base_sha": "167fa24accb0ff1b574a0a833786a6cdf22957d8",
  "authority": "docs/ACTIVE_MISSION.md"
}
-->

## Objective

Establish the first durable Kitty Project Control Plane / Continuity Foundation
so Jacob can brainstorm naturally with Kitty, approve a precise mission, and
hand execution to KittyBuilder without manually reconstructing context.

This mission ratifies the contract only. It does not add autonomous mutation or
a permanent project-manager agent runtime.

## Product decision

- Jacob interacts with Kitty, not a roster of worker models.
- Kitty is the principal agent: thinking partner, intent compiler, product
  lead, and project manager.
- Kitty selectively retrieves relevant context, identifies what is missing,
  challenges assumptions, plans evidence, and compiles an approval-ready
  mission.
- Kitty chooses whether to reason, retrieve, research, use tools or experts, or
  delegate an approved mission to Builder.
- KittyBuilder is the execution control plane. It owns decomposition, worker
  and model routing, context packaging, authority enforcement, budgets,
  attempts, validation, recovery, publication, and evidence.
- Models are replaceable workers. They do not own project truth.
- The system optimizes for verified truth and roughly 90–95% of the available
  quality at materially lower cost; expensive escalation requires evidence that
  the cheaper route is insufficient for the risk or reasoning need.
- Kitty should increase Jacob's independent capability through concise
  teach-back, visible decisions, and relevance-gated proactivity.

## Scope

1. Reconcile the architecture and canonical authority stack.
2. Ratify the Kitty → Mission → KittyBuilder boundary in an ADR.
3. Standardize `AGENTS.md`, `CLAUDE.md`, and `START_HERE.md` as bootloaders.
4. Normalize the active state and handoff files to one current checkpoint.
5. Implement deterministic `./kitty context --agent` receipts.
6. Share repository freshness enforcement with `./kitty doctor`.
7. Prove cold-start continuity from only the repository, receipt, and reading
   order.

## Authority granted

- Read the repository, local Builder state, Git history, and public GitHub
  repository state.
- Edit documentation, CLI/runtime source, and tests within this isolated branch.
- Run formatting, static checks, tests, link validation, and read-only doctors.
- Create small local commits.

The mission does not authorize push, merge, branch/worktree deletion, history
rewrites, secrets/auth/env changes, paid execution, heavy dependencies, or
autonomous Builder mutation.

## Evidence plan

- Record the refreshed `origin/main` SHA and isolated worktree identity.
- Derive context from Git, strict checkpoint metadata, the authority map, and
  supported Builder read projections.
- Unit-test stale HEAD, PR, branch/path, link, authority, Builder-description,
  and completed-action failures.
- Run targeted CLI/Builder tests, Ruff, mypy, link validation,
  `git diff --check`, and `./kitty doctor --json`.
- Give a clean model only the receipt and reading order and require correct
  answers to the eight cold-start questions.

## Acceptance contract

The mission is locally complete when the requested documentation and commands
work, freshness failures are explicit, validation evidence is recorded, and a
clean model can identify purpose, boundary, shipped state, active work, next
action, uncertainty, and authority without prior conversation.

Publication remains a separate human-authorized action. Until the work is
merged into `main`, the mission remains active with the next action owned by the
current session checkpoint.
