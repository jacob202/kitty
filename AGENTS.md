# Kitty — Agent Instructions

The documentation architecture begins at [`docs/INDEX.md`](docs/INDEX.md). Read it.

## Constitutional Rule

Every enduring idea has exactly one canonical home. Every other document references it. None duplicate it. Do not explain architecture here — point to it.

## Session Start

1. Read `.claude/HANDOFF.md` and `.claude/STATE.md`.
2. Read `docs/operations/PROJECT_STATUS.md` for current branch, shipped work, and test state.
3. Understand the current branch and any in-flight work before touching code.

## Prime Directive

Fail loud, never mask. Raise errors with clear causes. Do not swallow exceptions, return fake defaults, or add silent fallbacks. External calls may retry with a visible warning, then must raise the real error with useful context.

## Project Structure

Kitty is a local-first personal AI companion. Backend code lives in `gateway/`, FastAPI routes in `gateway/routes/`, path constants in `gateway/paths.py`. UI is `gateway/kitty-chat/` (Next.js). Tests in `tests/`. Runtime data in `data/`, logs in `logs/` — both uncommitted.

## Key Commands

```bash
./kitty up                                    # start Gateway and LiteLLM
./kitty down                                  # stop local services
./kitty status                                # process and health status
./kitty doctor --json                          # preflight checks
python3.12 -m pytest tests/ -q --tb=short     # Python suite
cd gateway/kitty-chat && npm run build         # UI production build
cd gateway/kitty-chat && npm test              # frontend tests
python3 scripts/docs_lint.py                   # documentation validation
python3 scripts/docs_system_map.py             # regenerate SYSTEM_MAP
```

Run docs lint and regenerate SYSTEM_MAP after adding, moving, or superseding any foundational document.

## Code Style

Match the existing file. Python: 4-space indent, explicit errors, small readable functions. TypeScript/React: functional components, clear prop names. Keep diffs focused; do not reformat unrelated code.

## Git and PRs

- Small Conventional Commit messages: `fix(auth): fail closed`.
- Never push, force-push, rewrite history, delete files, touch secrets/auth/payments/env, or add heavy dependencies without explicit confirmation.
- Before any `gh` or git push: check for stale `GITHUB_TOKEN`. If `env -u GITHUB_TOKEN gh auth status` succeeds, run GitHub commands with `env -u GITHUB_TOKEN`.
- Before merging a PR: read Actions **check runs** — confirm each required job is `success`, not just the combined commit status. See `docs/operations/LEARNINGS.md` L-CAND-6.
- After any non-trivial merge: compile/import touched files before declaring done.

## Builder

- Review `docs/builder/BUILDER_OPERATING_MODEL.md` before executing Builder work.
- Builder never invents architecture. If implementation requires architectural judgment: stop, collect evidence, escalate.
- T0 work: auto-approve. T1 work: separate model approval. T2 work: Jacob only (push, merge, deletes, auth/secrets/env, paid dependencies, broad scope).
- Same worker never approves its own work.
- Before multi-file work, give a short plan. Prefer editing existing files over creating new structure.

## Agent Rules

- **Research before invention.** Check whether something already exists in the repo, ADRs, or established patterns before building. See `docs/CONSTITUTION.md`.
- **Judgment before execution.** Read architecture and decisions before touching code. See `docs/architecture/REFERENCE_ARCHITECTURE.md`.
- **Reflection before closure.** Write `.claude/STATE.md` before stopping. Write `.claude/HANDOFF.md` if leaving unfinished work.
- **Small diffs.** One packet per session. Do not broaden scope.
- **Use Knowledge Model terminology.** See `docs/knowledge/KNOWLEDGE_MODEL.md`.

## Documentation Governance

See `docs/GOVERNANCE.md` for ownership, review, deprecation, and amendment rules. An ADR is required for: constitutional changes, new databases/queues/cloud services/frameworks, gateway API surface changes, approval tier changes, storage model changes, and cross-subsystem decisions. See `docs/adr/0000-template.md`.

## Where to Find Things

| Need | Go to |
|---|---|
| Why Kitty exists | `docs/VISION.md` |
| Engineering principles | `docs/CONSTITUTION.md` |
| Target architecture | `docs/architecture/REFERENCE_ARCHITECTURE.md` |
| Organizational model | `docs/architecture/ORGANIZATIONAL_MODEL.md` |
| Subsystem interactions | `docs/architecture/SYSTEM_INTERACTIONS.md` |
| Knowledge vocabulary | `docs/knowledge/KNOWLEDGE_MODEL.md` |
| Builder operating model | `docs/builder/BUILDER_OPERATING_MODEL.md` |
| Builder spec index | `docs/builder/BUILDER_SPECIFICATION_INDEX.md` |
| Builder packet lifecycle | `docs/builder/BUILDER_PACKET_LIFECYCLE.md` |
| Builder execution pipeline | `docs/builder/BUILDER_EXECUTION_PIPELINE.md` |
| Builder event model | `docs/builder/BUILDER_EVENT_MODEL.md` |
| Current runtime architecture | `docs/engineering/ARCHITECTURE.md` |
| All decisions | `docs/DECISIONS.md` |
| Current status | `docs/operations/PROJECT_STATUS.md` |
| Lessons learned | `docs/operations/LEARNINGS.md` |
| Documentation governance | `docs/GOVERNANCE.md` |
| Historical knowledge recovery | `docs/knowledge/HISTORICAL_KNOWLEDGE_RECOVERY.md` |
| Repository evolution | `docs/repository/REPOSITORY_EVOLUTION.md` |
| Full index | `docs/INDEX.md` |
