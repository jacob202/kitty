# Kitty's Unfair Advantage and Model Harness Roadmap

**Status:** future product direction and engineering strategy \
**Date:** 2026-07-14 \
**Relationship:** complements `KITTY_PRODUCT_ARCHITECTURE.md` and `FUTURE_CAPABILITIES.md`; references the Packet 028 reasoning engine and the KittyBuilder roadmap as related work. This is independent future product direction — not part of Packet 028.

## North-star promise

Kitty should feel like an unfair advantage.

That does not mean displaying more AI machinery. It means the user can understand a situation faster, make a better decision, start useful work with less effort, and recover from interruption without reconstructing context.

The experience should feel:

- **obvious:** the next useful action is easy to find;
- **powerful:** difficult work receives the right models, context, tools, and verification;
- **calm:** capability is progressively disclosed rather than dumped on screen;
- **continuous:** Kitty remembers the state of meaningful work and resumes it truthfully;
- **applicable:** answers turn into decisions, artifacts, plans, tasks, or completed work;
- **trustworthy:** every consequential claim or action has a short path to its evidence.

A capability is not successful because Kitty can technically perform it. It is successful when the user can understand and apply it without learning Kitty's internal architecture.

## Experience laws

1. **One obvious primary action.** Every surface should make the most useful next action visually dominant.
2. **Progressive disclosure.** Ordinary views use plain language. Technical detail is one tap away, not permanently visible.
3. **No dead ends.** Answers should offer a direct continuation when useful: apply, save, compare, build, schedule, verify, or resume.
4. **No fake simplicity.** Hiding failure is not simplicity. Failure, uncertainty, stale state, and approval needs must remain clear.
5. **No configuration tax.** Auto should work well. Manual controls exist for meaningful preferences, not every internal parameter.
6. **Power without babysitting.** Long work should run through durable, bounded systems with progress, recovery, and evidence.
7. **The system learns only through governed change.** Routing and policy may improve from evidence, but never drift silently.

---

# KittyBuilder as a first-class app tab

## Product decision

Kitty should have a primary **KittyBuilder** tab.

Do not require the user to infer that Builder lives inside a generic Work screen. The name has meaning, and the user should be able to open the app and visually understand what Kitty is building, what finished, what failed, and what needs approval.

The tab should have two disclosure levels:

- **Simple view:** plans, tasks, progress, blockers, decisions, results.
- **Advanced view:** packets, dependency graph, models, attempts, branches, worktrees, validation, review evidence, logs, hashes, and raw receipts.

The simple view is the default. Advanced detail is available without becoming the visual language of the whole app.

## KittyBuilder landing screen

The first screen should answer:

- What is Kitty building now?
- What changed since I last looked?
- What needs me?
- What is next?
- What was successfully shipped?

Recommended hierarchy:

1. **Active build card** — current initiative, plain-language goal, percent/phase, current task, elapsed time, and honest status.
2. **Needs you** — approvals, ambiguous decisions, blocked work, exhausted budgets, or review failures.
3. **Next up** — the next eligible packet and why it is next.
4. **Recently completed** — verified results with PR/artifact links.
5. **Health strip** — only visible by default when degraded.

## Initiative view

Present the initiative as a visual dependency map, but keep it readable:

- completed tasks collapse into a quiet summary;
- current and blocked tasks are emphasized;
- dependencies are visible without resembling a circuit diagram;
- each task card states objective, status, result, and blocker in human language;
- advanced expansion shows allowed paths, attempts, model, branch, validation, and review.

## Run detail

A run should read like a story:

1. Context prepared
2. Worker started
3. Files changed
4. Validation ran
5. Independent review completed
6. Repair attempted, if required
7. Result ready or blocked

The default timeline should omit noisy subprocess chatter. Raw logs remain available behind an advanced expansion.

## Actions

The tab should support:

- start an approved initiative;
- pause or resume;
- cancel safely;
- approve or reject a boundary decision;
- retry from a clean failure;
- inspect preserved partial work;
- take over manually;
- compare the current diff with the packet objective;
- run verification again;
- open the branch, PR, artifact, preview, or receipt;
- create a new build from a chat, issue, idea, or artifact.

## Build from anywhere

Any meaningful object should offer a contextual **Build with KittyBuilder** action:

- a chat request;
- a bug report;
- a roadmap item;
- a failed run;
- a design or screenshot;
- a GitHub issue;
- a decision journal entry;
- an artifact requiring implementation.

The action should first show the proposed goal, scope, acceptance criteria, cost/risk boundary, and packet plan. The user approves the plan, not a mysterious autonomous process.

---

# The model harness: every lever for more power and efficiency

The harness is the complete system around the model: context selection, task compilation, routing, tools, execution, verification, memory, recovery, evaluation, and UI. Improving the harness often produces more value than upgrading the model alone.

## 1. Context compiler

### Goal

Give each model exactly the context required for its stage—no less, and no giant undifferentiated repository dump.

### Improvements

- Build a durable repository map: modules, ownership, entry points, tests, migrations, routes, components, and dependency relationships.
- Use AST, symbol, reference, import, and call-graph retrieval rather than keyword search alone.
- Retrieve current code, relevant tests, recent changes, decisions, and packet constraints as separate typed context sections.
- Rank context by task relevance, authority, freshness, and risk.
- Deduplicate repeated snippets and contradictory stale documentation.
- Preserve exact source references so a model can request expansion rather than receiving everything up front.
- Allocate context budgets per stage: planning needs architecture; implementation needs exact files; review needs requirements plus diff and tests.
- Send context deltas on repair attempts rather than rebuilding the entire prompt.
- Use prompt/provider caching for stable repository instructions and shared context.
- Include negative context: forbidden paths, known traps, rejected approaches, and unresolved review findings.
- Detect when the packet lacks required context before spending a worker attempt.

### Power gain

Better context increases correctness, reduces hallucinated architecture, shortens prompts, and allows smaller models to perform like larger ones on bounded tasks.

## 2. Request and packet compiler

### Goal

Turn a human goal into an executable contract before implementation begins.

### Contract fields

- user objective and desired outcome;
- facts, assumptions, and unknowns;
- explicit scope and allowed paths;
- forbidden operations and ownership boundaries;
- dependencies;
- acceptance criteria;
- verification commands;
- required visual or runtime evidence;
- privacy, cost, time, and attempt budgets;
- rollback and recovery expectations;
- expected artifacts and receipt.

### Improvements

- Add a packet linter that detects vague objectives, untestable acceptance criteria, overly broad paths, contradictory constraints, and missing verification.
- Estimate packet complexity and split oversized packets before execution.
- Trace every acceptance criterion to one or more tests or evidence checks.
- Generate an implementation-risk map: migrations, auth, concurrency, data loss, public API, UI state, and external effects.
- Require a small proof-of-understanding from the worker before editing when the packet is high-risk.
- Keep planning and implementation separate when architecture is not settled.

## 3. Model capability registry

### Goal

Route by demonstrated capability, not reputation or one global ranking.

### Registry dimensions

Track each model/provider by:

- code understanding;
- implementation accuracy;
- debugging ability;
- frontend/UI ability;
- test writing;
- review quality;
- long-context reliability;
- instruction adherence;
- tool use;
- speed;
- cost;
- rate limits and availability;
- privacy/execution location;
- failure signatures;
- performance by repository and packet class.

### Routing improvements

- Select models independently for planning, implementation, review, repair, and synthesis.
- Prefer the cheapest model that clears the quality threshold for the task class.
- Pin models only when reproducibility or a known strength matters.
- Fall back only after a clean failure with no partial work.
- Never hand a dirty worktree to a fallback model without explicit continuation context.
- Use provider health and live availability in routing.
- Treat local models as first-class for classification, extraction, search, summarization, and privacy-sensitive work.
- Reserve expensive models for architecture, ambiguous failures, high-risk review, and difficult synthesis.

## 4. Adaptive budget allocator

### Goal

Spend reasoning, tokens, time, tools, and money where they change the outcome.

### Improvements

- Establish Fast, Balanced, Deep, and Auto execution profiles.
- Set separate budgets for planning, implementation, validation, review, and repair.
- Increase budget from observable task signals: breadth, novelty, risk, failing tests, cross-layer changes, weak context, and prior failed attempts.
- Reduce budget for mechanical edits with strong tests and narrow scope.
- Stop early when acceptance criteria are satisfied and review is clean.
- Escalate only one bounded step at a time.
- Make paid escalation an explicit policy decision.
- Record estimated and actual budget consumption in receipts.
- Compare quality/cost Pareto frontiers rather than simply maximizing model size.

## 5. Stage-specialized agents

### Goal

Avoid asking one context-bloated agent to plan, code, test, and approve its own work.

### Roles

- context curator;
- planner/spec compiler;
- implementer;
- test designer;
- verifier;
- adversarial reviewer;
- repair worker;
- final synthesizer.

These are roles, not necessarily separate models or processes every time. The policy engine should activate only the roles justified by task complexity.

### Guardrail

The implementer never becomes the sole approver of its own work. Independent review must receive the original requirements, actual diff, validation evidence, and known risks.

## 6. Tool harness

### High-value tools

- language servers and symbol/reference lookup;
- AST-aware structural search and edits;
- code graph and dependency analysis;
- git blame/history scoped to relevant lines;
- changed-test selection;
- type checking and linting early in the loop;
- database migration validation;
- browser and screenshot verification;
- accessibility checks;
- API contract probes;
- log and trace inspection;
- performance and memory profiling when relevant;
- deterministic file and artifact hashing;
- sandboxed shell execution;
- isolated worktrees and ephemeral test environments.

### Tool policy

- expose only tools relevant to the stage;
- provide typed outputs instead of huge terminal dumps;
- summarize routine success and preserve full logs as artifacts;
- make destructive and external-effect tools approval-gated;
- collect tool latency, reliability, and usefulness metrics;
- retry tools only when the error is classified as transient and no unsafe partial effect occurred.

## 7. Change-aware validation

### Goal

Get faster feedback without weakening the final gate.

### Validation ladder

1. syntax/parse checks;
2. targeted lint and type checks;
3. nearest unit tests;
4. dependency-aware affected tests;
5. integration or browser checks required by the packet;
6. full repository-required gate before publication.

### Improvements

- Map changed symbols and paths to likely tests.
- Run cheap deterministic checks immediately after each meaningful edit.
- Cache unchanged build and dependency layers.
- Parallelize independent validations.
- Detect flaky tests and distinguish them from product failures without ignoring either.
- Require visual evidence for visual acceptance criteria.
- Compare screenshots or DOM states where appropriate.
- Preserve all validation results as structured receipts.

## 8. Requirement-to-evidence traceability

### Goal

Make “done” mechanically difficult to fake.

For every acceptance criterion, record:

- implementation location;
- validating test or command;
- runtime or visual evidence;
- reviewer verdict;
- unresolved caveat.

A packet is complete only when every required criterion has accepted evidence. Process exit alone is never sufficient.

## 9. Independent and adversarial review

### Improvements

- Give the reviewer the original packet, not the implementer's summary alone.
- Review the aggregate diff against the true base.
- Check scope, architecture fit, security, failure semantics, tests, accessibility, performance, and user experience.
- Use a different model or provider when practical to reduce correlated mistakes.
- Generate counterexamples and failure cases for risky logic.
- Require explicit verdicts per acceptance criterion.
- Separate defects from optional polish so repair loops remain bounded.
- Track reviewer precision: findings later confirmed, rejected, or missed.

## 10. Bounded multi-candidate execution

### Goal

Use parallel intelligence only where diversity is worth the cost.

### Appropriate uses

- architecture alternatives;
- difficult debugging with several plausible root causes;
- UI concept generation;
- migration strategies;
- high-stakes review;
- optimization with measurable trade-offs.

### Pattern

Generate two or three bounded candidates, evaluate them against the same rubric, and synthesize or select. Do not run redundant models on routine work.

## 11. Failure memory and institutional learning

### Goal

KittyBuilder should not repeatedly rediscover the same repository traps.

### Store

- failure signature;
- root cause;
- affected subsystem;
- successful repair;
- rejected repairs;
- relevant commits and tests;
- whether the lesson remains current;
- confidence and source evidence.

### Retrieval

Inject only task-relevant lessons. Never append an ever-growing chronological scratchpad to every prompt.

### Examples

- stale database state versus merged GitHub state;
- dirty-worktree preservation rules;
- model fallback only after clean failure;
- shell launcher versus Python module invocation;
- worktree identity assumptions;
- provider-specific reasoning parameters;
- known local-environment test failures.

## 12. Durable recovery and reconciliation

### Improvements

- Make every run idempotent and resumable.
- Persist stage transitions before side effects.
- Detect and preserve partial work.
- Reconcile Builder database state with Git branches, worktrees, PRs, reviews, and merges.
- Distinguish stale, abandoned, active, exhausted, completed, and externally completed work.
- Add a visual recovery assistant that explains the safest next action.
- Snapshot critical queue state before migrations or repair operations.
- Never silently recreate an initiative or duplicate already-merged work.
- Run doctor checks before every execution, not only by manual command.

## 13. Parallelism scheduler

### Goal

Run independent work concurrently without creating merge chaos or exhausting the machine.

### Improvements

- Build a packet dependency DAG.
- Detect path and symbol overlap before parallel launch.
- Respect CPU, RAM, disk, provider, and rate-limit budgets.
- Serialize migrations, shared configuration, and high-conflict files.
- Parallelize independent tests and read-only research.
- Reserve resources for the foreground user experience.
- Recalculate eligibility after every merged or externally completed packet.

## 14. Prompt and context efficiency

### Improvements

- Stable system instructions cached once.
- Compact typed contracts instead of repeated prose.
- Context references with on-demand expansion.
- Delta prompts for repair loops.
- Aggressive removal of duplicated logs and stale summaries.
- Stage-specific prompts.
- Structured tool outputs.
- Automatic conversation compaction that preserves decisions, constraints, and unresolved questions rather than raw transcript volume.
- Token accounting by context category to identify waste.
- Provider prompt caching when supported.

## 15. Repository-aware editing

### Improvements

- Prefer minimal, localized changes.
- Use structural edits for repetitive refactors.
- Detect generated files and ownership boundaries.
- Update tests and documentation alongside behavior.
- Run formatter only on touched scope unless repository policy requires otherwise.
- Check for duplicate abstractions before adding new modules.
- Compare proposed interfaces with existing conventions.
- Track semantic change, not merely line count.

## 16. UI and browser verification harness

### Improvements

- Launch the real app in an isolated test profile.
- Navigate core user journeys automatically.
- Capture screenshots and DOM/accessibility snapshots.
- Verify loading, empty, success, error, reconnecting, and mobile states.
- Check keyboard behavior, focus, screen-reader labels, and responsive layout.
- Compare visual output against acceptance references.
- Attach evidence directly to the run and PR.
- Treat browser QA as a release gate for user-visible packets.

## 17. Security and authority harness

### Improvements

- Keep credentials out of worker environments unless explicitly required.
- Redact secrets from logs, artifacts, and prompts.
- Sandboxed filesystem and network boundaries.
- Per-packet tool and path allowlists.
- Explicit approval for push, merge, deletion, paid execution, external messages, auth, and environment changes.
- Dependency and supply-chain checks for new packages.
- Data classification before cloud routing.
- Immutable audit trail for approvals and external effects.

## 18. Benchmark and evaluation system

### Goal

Know whether the harness is actually improving rather than merely becoming more elaborate.

### Benchmark dimensions

- task success;
- acceptance-criterion completion;
- defect rate after review;
- regression rate after merge;
- human takeover frequency;
- latency;
- tokens and cost;
- number of attempts;
- fallback and infra-failure rates;
- review precision and recall;
- context utilization;
- user correction and satisfaction;
- ability to resume after interruption.

### Evaluation design

- Maintain representative packet suites by task class.
- Replay historical failures as regression cases.
- Compare models and policies on identical bundles.
- Separate model quality from harness quality.
- Track results by repository version and environment.
- Use canary policy changes before broad promotion.
- Publish a simple quality/cost dashboard in KittyBuilder.

## 19. Governed harness self-improvement

### Goal

Let KittyBuilder improve its own routing and workflows without uncontrolled self-modification.

### Loop

1. Detect a repeated inefficiency or failure pattern.
2. Produce a proposed harness change and expected metric improvement.
3. Build a bounded test or benchmark.
4. Implement in an isolated branch.
5. Run historical and current evaluations.
6. Obtain independent review.
7. Promote a versioned policy or harness release after approval.
8. Retain rollback and comparison data.

No silent prompt mutation, no live policy drift, and no self-approval.

## 20. Human leverage features

The strongest harness is not only autonomous. It makes the human dramatically more effective.

Add:

- one-tap explanation of why a run is blocked;
- visual diff summaries focused on behavior;
- suggested approval with risk and reversibility;
- editable plan and packet before launch;
- `show me the risky parts`;
- `compare implementation to objective`;
- `take over here`;
- `continue with this instruction` without restarting the whole run;
- save a successful workflow as a reusable template;
- turn a review finding into a repair packet;
- turn a completed run into a decision-journal outcome.

---

# Highest-leverage build order

## Tier 0 — make the current system truthful and operable

1. Builder/GitHub/worktree state reconciliation
2. Doctor preflight automatically enforced before every run
3. Partial-work preservation and visual recovery
4. Requirement-to-evidence completion rules
5. Capability Manifest and execution receipts

## Tier 1 — create the unfair-advantage experience

1. First-class KittyBuilder tab
2. Active build, Needs You, Next Up, and Recently Completed views
3. Visual initiative dependency map
4. Run story/timeline with progressive disclosure
5. Build-from-chat and build-from-object flow
6. Pause, approve, retry, recover, inspect, and take-over actions

## Tier 2 — increase model performance per token

1. Context compiler and repository map
2. Packet compiler and packet linter
3. Stage-specific context and prompts
4. Model capability registry and task-specific routing
5. Adaptive budgets and clean-failure fallback
6. Changed-test selection and cached validation
7. Failure memory retrieval

## Tier 3 — increase quality ceiling

1. Independent adversarial review
2. Browser/runtime evidence harness
3. Multi-candidate execution for high-value ambiguity
4. Simulation and strategy comparison
5. Benchmark-driven policy optimization
6. Governed harness self-improvement

# Success test

KittyBuilder has succeeded when the user can open one tab and immediately understand:

- what Kitty is building;
- why it is doing that;
- what has happened;
- whether the result is trustworthy;
- what needs the user;
- what the safest next action is.

The harness has succeeded when a modest model with the right context, tools, policy, and verification routinely outperforms a larger model operating as a context-blind chatbot—and when a larger model becomes dramatically more capable rather than merely more expensive.
