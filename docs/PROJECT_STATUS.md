# Project Status

**Verified:** 2026-07-28 against `origin/main` at `0a2a04480ecd555168656de62dfa9a3cc971031f`.

Branch, worktree, dirty state, relation to `origin/main`, and local Builder state must be derived from `./kitty context --agent` and supported Builder commands. They are not copied here as live facts.

## Shipped product and infrastructure

Repository evidence shows substantial working capability across:

- FastAPI gateway surfaces for chat, memory, capture, brief, projects, settings, image, tutor, voice, integrations, and Builder investigation;
- a Next.js product shell with shared runtime/provider attribution and error handling;
- consolidated application storage plus unified memory reads through `memory_graph`;
- model/provider routing with explicit provider selection, fallback behavior, and truthful runtime metadata;
- durable Builder queues, attempts, leases, validation, recovery rails, worker identity checks, initiative tooling, operator controls, and PR publication;
- CI gates for Python tests, typing, lint, hygiene, frontend tests/build, and browser smoke.

The 2026-07-28 merge of PR #288 hardened runtime lifecycle truth, provider/tool state, attribution, and explicit AgentRouter routing. This is repository evidence, not proof that every configured provider or local runtime is currently healthy.

## Current open repository work

At verification time, PR #289 was open with a broad change set covering Builder reliability, frontend/backend alignment, an ImagePlan boundary, provider metadata, and model-routing refactoring. Its live mergeability, CI status, review state, and final scope must be read from GitHub before action.

No older PR list in archived status documents should be treated as current.

## Builder state

The Builder database and execution evidence are local runtime state. They are not available from repository prose or GitHub alone, so current initiatives, packets, attempts, leases, provider exhaustion, and publication state are **unknown here**.

Use supported projections such as:

```bash
./kitty context --agent
./kitty builder initiative doctor --json
```

An absent or inaccessible runtime database is unknown/unused, not an empty success.

## Current authority and priority

- Product purpose: `docs/NORTH_STAR.md`.
- Architecture: `docs/ARCHITECTURE.md` plus accepted ADRs.
- Delivery order: `docs/ROADMAP.md` only.
- Approved work: `docs/ACTIVE_MISSION.md` only.
- Live continuation: `.claude/STATE.md` and `.claude/HANDOFF.md` only while their identity metadata remains valid.

Plans, packets, research, old session trackers, and archive material are inputs or history. They do not become active merely because they are detailed.

## Known limitations

- Daily-use reliability and product coherence still lag behind the breadth of backend capability.
- Repository evidence cannot prove local provider credentials, quotas, process health, or Builder runtime state.
- Broad PRs can blur verification boundaries; review PR #289 by subsystem and evidence rather than trusting its summary as one atomic claim.
- A generated code bundle is a navigation aid, not runtime truth. Review it for secrets and staleness before uploading.

## Navigation

Use `START_HERE.md` for cold start, `docs/README.md` for documentation routing, `docs/CODEBASE_MAP.md` for code navigation, and `docs/archive/README.md` for historical material.
