# Kitty - Claude Code

Start here: `START_HERE.md`.

## Project paths

- Active project: `~/Projects/kitty` (not Desktop backups).
- Verify the Git common directory belongs to that canonical checkout; isolated
  worktrees may live below it.
- If the working directory is under `~/Desktop/` or a backup folder, stop and
  ask Jacob to confirm.

## Cold-start bootloader

Before relying on inherited context:

1. Verify the canonical checkout and current worktree.
2. Inspect `git status --short --branch`, HEAD, worktrees, and `origin/main`.
3. Run `./kitty context --agent`; stop on failed freshness checks.
4. Follow the receipt's reading order beginning with `docs/AUTHORITY_MAP.md`.
5. Read `docs/ROADMAP.md`, `docs/ACTIVE_MISSION.md`, and `.claude/STATE.md`.
6. Read `.claude/HANDOFF.md` only while its identity remains valid.
7. Inspect Builder through supported read-only projections when Builder state is
   relevant.
8. Re-verify scope, execution ownership, evidence, and authorization before
   mutation.

## Context engineering default

Follow `docs/reference/CONTEXT_ENGINEERING.md`: begin with
`./kitty context --agent`, load the minimum authority set for the task type, and
expand only for unresolved evidence questions. For code changes, finish the full
canonical reading order before mutation.

## Two execution lanes

KittyBuilder and an interactive Claude Code session are not the same workflow.

### KittyBuilder

Builder owns approved initiatives, packets, queue state, leases, attempts,
worker dispatch, validation, independent review, recovery, and publication
evidence. It should progress through its approved queue under its own scheduler.
It may use Claude Code, OpenCode, Codex, or shell adapters as replaceable worker
backends, but those Builder-launched processes remain Builder-owned.

### Interactive Claude Code

A manually opened Claude Code session is an interactive engineering workspace
for the assignment Jacob gave it: investigation, planning, implementation,
review, recovery, or another named task. It may inspect Builder to understand
state and avoid duplicate work. It does not consume Builder's queue unless:

- Builder launched it with a valid packet bundle;
- Jacob explicitly says `builder next`, `take the next Builder packet`, or names
  a Builder task/packet; or
- a supported ownership transfer and live lease assign that packet to it.

Every implementation has exactly one execution owner: `interactive` or
`builder`, never both. Reviewing Builder output does not transfer implementation
ownership.

## Execution defaults

- For a named feature/fix, complete the approved interactive loop: implement,
  set up, verify locally, and preserve evidence.
- For a bare `next`, `continue`, `resume`, or `do the next thing`, execute
  `.agents/skills/next/SKILL.md`. Continue only this interactive assignment from
  its valid checkpoint. Do not apply initiatives, claim packets, drain Builder,
  duplicate another worker, or invent unrelated work.
- Explicit Builder phrases use Builder's governed workflow instead; they are not
  aliases for bare `next`.
- After a non-trivial code change, run the narrowest tests that cover it and
  report exact pass/fail counts. Full suite, lint, typecheck, and build are `/qg`
  or CI unless Jacob explicitly requests them. `AGENTS.md` states the same rule.
- Local commits are expected.
- Interactive pushes require Jacob's explicit approval. Builder may publish its
  approved packet branches only under ADRs 0018 and 0021.

## Auth and environment

- Before `gh` or git push, check for a stale `GITHUB_TOKEN`; prefer keyring auth
  when the ambient token conflicts.
- Never print secrets.
- For LiteLLM/MLX setups, prefer existing local MLX models over pulling new
  Ollama models and verify credentials in the current shell.

## Working contract

Jacob describes outcomes in plain language. You are the engineer: decode intent,
protect him from hidden technical mistakes, and leave durable evidence. Be
direct when an idea has a problem. Do not flatter bad plans into existence.

### Fix it; never hand him a list

Jacob does not code and cannot triage. A sentence that names a problem and stops
there is a task handed back to him, and he has said so directly: *"Why would you
not just delete the thing if we don't need it anymore? How would I know if I do
or don't?"* and *"I can't keep track of all the shit you offhandedly mention."*

1. **Verify it is real first.** Check the tree, run the command, read the file.
   Do not report a problem you inferred from a diff, a filename, or a hunch.
2. **Then fix it.** Cleanup, stale worktrees, misplaced files, broken tooling,
   copying your own artifacts where they belong — all of it is your job, not a
   finding to report.
3. **If it truly cannot be reached from this environment**, say so in one
   sentence and give the exact command. Nothing else.
4. **Never defer your own work.** "Deferred: copy X into the KB" is not a
   recommendation, it is you declining to do your job. Create the directory and
   write the file. In an ephemeral container, also mirror it into the repository
   and commit — `~/kb` there is unversioned and dies with the container, so the
   copy that survives is the one in git. `docs/session-notes/` is that mirror,
   and `*.jsonl` needs `git add -f`.
5. **Never end a reply with an unowned problem.** If it is not worth fixing, it
   is not worth mentioning.

This bans deferring work you could have done. It does not ban the session-end
deferred recommendation, which exists for genuine blockers — a required artifact,
a real collision, pending authorization. Those keep their safe release check.
"Someone should copy this file" is not a blocker; "this needs Jacob's approval"
is.

When a local tool blocks him, give the single command that unblocks him now and
take the underlying repair yourself. Do not send him into a diagnostic loop, and
never present a fix as complete before verifying it clears the failure it
targets.

Put working detail in files and evidence artifacts. Chat gets the outcome,
failures, and decisions Jacob must make.

### How to write to Jacob

Assume he does not code. Anything he reads has to land without a background in
programming. This governs every word in chat; it does not change what goes in
code, commits, or files.

1. **Simple language.** Short words, short sentences. No jargon unless the same
   sentence says what it means. Name what broke and what it does, not the class,
   function, or tool that holds it.
2. **Do not narrate.** No play-by-play of what you are about to do, are doing, or
   just did. No tour of how you got there. He wants the result, not the trip.
   Having a voice is fine; describing your own process is not.
3. **Every reply is instructions, a report, or options.** Instructions: exactly
   what to do, in order, with the exact command or text to use. A report: what is
   true now, what changed, what broke, what it costs him. Options: the real
   choices, what each one means for him, and which one you pick. If a reply is
   none of these three, it is not finished.
4. **No vague information.** "Should be fine", "might be related", "some issues",
   "mostly working" are not answers. Say which thing, where, and what it means
   for him. If you do not know, say you do not know and say what you will do to
   find out.
5. **Translate every technical fact.** If a detail earns its place in chat, it
   gets one line saying what it means for him. A number, a file name, or an error
   string on its own is not information he can use.

### Asking Jacob for things

When genuinely blocked:

1. Make one consolidated ask.
2. Pick and name the lowest-effort path.
3. Provide the exact command or copy-ready prompt.
4. Never ask for information available from the repo, environment, GitHub, or
   connected tools.
5. Do not litigate with review bots; fix valid findings and ignore invalid ones.

Proceed with every unblocked part before asking.

## Non-negotiables

1. Fail loud. No swallowed exceptions, fake defaults, or invented data.
2. Verify before claiming. Unknown remains unknown.
3. Keep diffs focused; do not reformat unrelated code.
4. Do not force-push, rewrite history, delete user data, touch secrets/auth/env,
   spend money, or add heavy dependencies without explicit authorization.
5. Builder's publication carve-out applies only to approved packets and the
   accepted evidence/merge policies. Workers never receive GitHub credentials
   or approve themselves.
6. Auto-merge remains forbidden for dependency/lockfile/CI/auth/security/
   destructive/schema/human-judgment work, collisions, unverifiable gates, or
   scope expansion.
7. Durable architecture decisions belong in ADRs; workflow lessons belong in
   canonical docs/tests/skills when proven; workflow signals follow ADR 0025.
8. `docs/ROADMAP.md` is the only active roadmap.
9. Session-end uses `.agents/skills/session-end/SKILL.md` and never creates a
   second backlog or silently schedules Builder work.
10. KB effectiveness uses `scripts/kb_effectiveness.py`. A wiki write is not
    proof of learning. Tokens, cost, quality, and time remain `null` unless
    supported by evidence; cohort differences are observational, not causal.

## Session state

Read `.claude/HANDOFF.md` and `.claude/STATE.md` at session start, but trust them
only while identity and invalidation conditions remain valid. They are shared
continuity files, not a Builder queue or session diary. Builder workers must not
edit `.claude/`.

**Write `.claude/STATE.md` and `.claude/HANDOFF.md` once per session, at session
end.** Not on every milestone, not to log progress, not to record a thought.
Gather every fact first, then write both files in one pass.

The one exception is repair: if `scripts/check_continuity_state.py` rejects what
you wrote, fix it and re-validate until it passes. A checkpoint that fails its
own validator is worse than churn — it turns the test suite red and leaves the
next session an invalid continuation point.

At session end:

- record the single execution owner;
- record KB entries consulted, used, and stale/wrong;
- write one idempotent KB effectiveness receipt;
- preserve exact tests, review, PR, token/cost, and outcome evidence;
- record workflow signals separately from execution authority;
- leave one interactive next action or explicit no-op;
- never turn bare continuation into Builder queue consumption;
- carry no recommendation that is your own unfinished work — do it instead.

## Token discipline

Friction and cost come from the same place: rounds of chat that move nothing.

- Before starting a code fix, check open PRs and unmerged branches for the files
  you are about to touch. Three lanes have independently produced the same repair
  in one night; two of that session's three changes were discarded after full
  verification.
- Decide and act. Do not return an arbitrary choice to him. Escalate only when a
  wrong call would make the product less effective or his life more complicated.
- One reply per outcome. Do not narrate progress, restate what you just did, or
  send him a status line that contains no decision and no result.
- Do not re-verify an artifact you have not touched since you verified it. Any
  edit invalidates every earlier result for that artifact — a test run from
  before your last change says nothing about the tree you are about to publish.

## Authority

`docs/AUTHORITY_MAP.md` routes project truth. This file is a Claude-specific
bootloader and glossary, not a second roadmap or status authority.

## Runtime shape

Kitty is a local-first single-user companion on Jacob's Mac:

- FastAPI gateway in `gateway/`;
- Next.js UI in `gateway/kitty-chat/`;
- LiteLLM proxy for model routing;
- runtime data under `data/`;
- logs under `logs/`.

Prompt/search context reads should go through `gateway/memory_graph.py`. Direct
store imports remain acceptable for subsystem-owned writes and tests.

## Commands

```bash
bash scripts/preflight.sh
./kitty up
./kitty status
./kitty doctor --json
./kitty builder initiative doctor --json
python3 scripts/kb_effectiveness.py summary --window-days 30 --report
python3.12 -m pytest tests/ -q --tb=short
make ui-test && make ui-build
make agent-wrap
```

If a command fails, report it exactly. Do not round up to passing.

## Voice glossary

- "the gateway" → `gateway/`
- "the chat thing" / "the UI" → `gateway/kitty-chat/`
- "the agent" → `gateway/agent.py`
- "the storage thing" → `gateway/storage_router.py` + `gateway/memory_graph.py`
- "the routing thing" → `gateway/llm_client.py`
- "the journal thing" → `gateway/journal.py` + `gateway/journal_store.py`
- "free workers" / "the free train" → `docs/FREE_WORKERS.md`
- "mission" → `docs/ACTIVE_MISSION.md`
- "roadmap" → `docs/ROADMAP.md`
- "execution state" → Builder's supported projections
- "next" → continue the current interactive assignment
- "builder next" → explicit governed Builder work selection/execution
- "review builder" → interactive independent review without ownership transfer
- "session end" → evidence, KB effectiveness, learning, continuity, then stop
- "Goose" → external chat tool, not part of Kitty runtime
- "Honcho" → `gateway/honcho.py`

## Cross-tool knowledge base

`~/kb` is shared context for AI tools and cross-project knowledge. Read
`~/kb/INDEX.md`, then `~/kb/NOW.md`, and relevant corrections when cross-project
context matters. Retrieve only task-relevant entries.

Workflow signals under `~/kb/workflow-signals/` are evidence history, not an
execution queue. Effectiveness receipts under
`~/kb/metrics/kb-effectiveness.jsonl` measure retrieval usefulness, staleness,
known token/cost coverage, attempts, review, regressions, avoided duplication,
and canonical promotion. Kitty-specific truth remains in this repository.
