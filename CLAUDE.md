# Kitty - Claude Code

Start here: `START_HERE.md`.

## Project paths

- Active project: `~/Projects/kitty` (not Desktop backups).
- Verify the Git common directory belongs to that canonical checkout; isolated
  worktrees may live below it.
- If the working directory is under `~/Desktop/` or a backup folder, stop and
  ask Jacob to confirm.

## Cold-start bootloader

`START_HERE.md` owns the cold-start procedure: checkout/worktree verification,
live Git state, the context receipt (GAR `--skip-legacy-continuity` vs. strict
legacy fallback), the authority reading order, and the final mutation gate. Run
it before relying on inherited context instead of restating it here.

## Global Agent Room

For Kitty work, `workspace_global` is the default durable communication channel
with Jacob, ChatGPT, Codex, and Kitty. With the configured Agent Room MCP, use
`room_status`, `room_recent`, `room_inbox`, `room_thread`, `room_post`,
`room_reply`, and `room_ack`. The MCP identity is pinned; do not impersonate
another participant.

At start/resume, use unread direct messages and a known thread id as the durable
locator for the assignment; do not assume the newest global messages contain an
older active handoff. During work, use direct messages for a specific owner,
broadcasts when everyone needs the information, and thread replies for
continuations. Before stopping substantial work, post the final verified result
or handoff only after final validation. `registered` means membership only,
never online presence. The room is communication, not execution: Builder owns
engineering tasks/leases, #490 owns interactive collision/ownership, and
Git/GitHub own publication evidence.

## Context engineering default

Follow `docs/reference/CONTEXT_ENGINEERING.md`. With a known GAR handoff/thread,
begin with `./kitty context --agent --skip-legacy-continuity`, load the minimum
authority set for the task type, and expand only for unresolved evidence
questions. If no durable GAR locator exists and legacy fallback is required, or
if GAR is unavailable, use strict `./kitty context --agent` before trusting the
checkpoint. For code changes, finish the full canonical reading order before
mutation.

## Two execution lanes

Builder vs. interactive ownership is shared doctrine: `AGENTS.md` owns the
Builder ownership rules and the single-owner lane contract. Claude-specific
defaults follow.

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
- Push requires explicit authorization from Jacob — never push autonomously.
  Once authorized, the path is branch, push, open a PR, then handle CI and
  review without pinging Jacob. Report after, not before. Builder may publish
  its approved packet branches only under ADRs 0018 and 0021.

## Reviewer routing

Reviewer routing is shared doctrine; `AGENTS.md` owns the OpenRouter
price-first rule, the single clean different-model fallback, model-family
independence, and the `--free` no-paid-fallback guarantee. Apply it for
merge-blocking, product-acceptance, and other independent review.


## Auth and environment

- Before `gh` or git push, check for a stale `GITHUB_TOKEN`; prefer keyring auth
  when the ambient token conflicts. If git cannot find a credential helper, push
  with `git -c credential.helper='!gh auth git-credential' push`.
- Never apply an approval or risk label to a PR you authored. Jacob holds the
  approval keys; ask him. Autonomy belongs in execution, never in permission.
- Read the current required checks (`gh api repos/:owner/:repo/rulesets`) before
  opening or merging a PR. Check names have been restructured mid-session
  before; assuming last session's names produces confident, wrong triage.
- Never print secrets.
- For LiteLLM/MLX setups, prefer existing local MLX models over pulling new
  Ollama models and verify credentials in the current shell.

## Working contract

Jacob describes outcomes in plain language. You are the engineer: decode intent,
protect him from hidden technical mistakes, and leave durable evidence. Be
direct when an idea has a problem. Do not flatter bad plans into existence.

### Diagnosis discipline

Before calling anything broken, check whether it was ever started or configured
at all, and read `git status` for deletions someone staged on purpose. Say which
one it is in the first sentence: not running is a different problem from
failing, and a thing nobody ever turned on is a third. Both mistakes have
already been made here — a staged lint-config deletion was reported as breaking
when the config was dead, and Builder's real fault was that no scheduled tick
had ever existed.

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
   recommendation, it is you declining to do your job. Write the file now, into
   the store that actually applies.

   **Never create `~/kb` yourself.** The real knowledge base is Jacob's, on his
   Mac, and it already has history. `resolve_store()` in
   `scripts/kb_effectiveness.py` and `scripts/session_learning.py` selects
   `~/kb` the moment that path is a directory, so making an empty one in a
   container silently redirects every receipt and signal into unversioned
   storage that dies with the container — and leaves behind a convincing-looking
   "knowledge base" holding nothing but your own session. When `~/kb` is absent
   the recorders already fall back to `docs/session-notes/`, which is in git and
   survives. Write there and commit; `*.jsonl` needs `git add -f`. An absent
   `~/kb` is a fact to report, never a gap to paper over.
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

The shared engineering limits — fail loud, verify before claiming, focused
diffs, no force-push/history-rewrite/secret/auth/env/irreversible actions, the
Builder publication carve-out, auto-merge prohibitions, ADR/workflow-signal
routing, and the session-end skill routing — are owned by `AGENTS.md`. Do not
restate them; apply them.

## Continuity compatibility

`workspace_global` is the primary live cross-agent and cross-session continuity
surface. Prefer unread direct handoffs and known threads over loading a whole
shared checkpoint file. Mutable current status and handoffs should be posted
there only after their final validation evidence is known.

`.claude/STATE.md` and `.claude/HANDOFF.md` remain tracked compatibility
artifacts while existing validators, adapters, and the session-end workflow still
consume them. They are not the default source for current coordination and must
never override fresher room, Git, GitHub, Builder, or runtime evidence. Do not
manually rewrite them during ordinary work. If no durable room locator exists
yet and legacy fallback is required, run the strict context receipt and trust
them only when that validation succeeds. If the session-end skill requires a
compatibility snapshot, write it once at the end, validate it, and keep it
minimal. Builder workers edit these files only when their packet explicitly owns
those paths.

If a legacy checkpoint is used, verify branch, HEAD, worktree, PR, timestamp,
and invalidation conditions before relying on it. The `merge=ours` driver remains
a compatibility safeguard for those files, not a reason to use them as a live
multi-agent mailbox.

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
- "the agent" → the autonomous agent subsystem, now split across
  `gateway/agent_runner.py` (spawns/runs LLM-driven goal agents),
  `gateway/agent_room_cli.py` (canonical global agent room CLI), and
  `gateway/agent_workspace.py` (durable shared rooms); the former single-file
  form is gone, so do not invent one
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
