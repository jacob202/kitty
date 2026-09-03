# kittybuilder redesign: 2026-07-24

> **position in the kit**: concrete implementation plan for the builder subsystem. takes input from `architecture-honesty.md` (what exists: mature builder_queue, pre-alpha builder_runner, existing agent_runner presets), `repo-landscape.md` (patterns to steal: skillopt rollout→validate→edit, 12-factor-agents human-in-the-loop), and `kitty-vision-gap-analysis.md` (autonomous execution is a p0-p1 gap).

redesign proposal based on code analysis of builder_queue.py (line 1-300, kb-s1 state machine), builder_runner.py (~200 lines, worktree sandbox), builder_loop.py (repair loop), builder_initiative.py (initiative parser), builder_status.py (status projection), builderpy.py (facade), and cross-referenced with agent_runner.py (508 lines, 5 presets, 6-phase reasoning) and context_assembler.py (383 lines, partial-result contract).

---

## current state — what exists

### builder_queue.py — mature, our foundation
- kb-s1 sqlite state machine: pending → active → done | paused | abandoned | error_edge
- packet model: each queue item references an initiative by id
- item-level status tracking
- background repair loop in builder_loop.py detects stalled items, transitions to abandoned or restarts
- this is the most carefully engineered queue in the codebase

### builder_runner.py — pre-alpha, the weak link
- worktree-based sandboxed execution with shadow mode
- clones worktree, executes python script, parses structured output
- single-shot only. no context about initiative goal/criteria/history. no result validation. no retry. no sub-task spawning.
- marked "phase 1c-alpha" in code

### builder_initiative.py
- parses initiative manifests: markdown with yaml frontmatter
- single parser (markdown). no schema validation. no pydantic models.

### builder_status.py
- read-only projection from queue store
- returns queue item status only. no initiative-level progress aggregation (e.g., "3 of 5 tasks complete").

### builderpy.py
- thin facade: initializes queue, loop, runner, status into one object
- adds no behavior. callers can import components directly.

### related infrastructure (not currently connected)
- `agent_runner.py`: 5 presets (explorer, planner, coder, reviewer, researcher) with 6-phase reasoning loop and autonomy_state.db persistence. **these presets are builder sub-task types waiting to be wired.**
- `context_assembler.py`: partial-result contract (individual source failures → warnings, never exceptions). **this contract should govern builder result handling.**
- `memory_consolidation.py`: nightly_dream pipeline (cluster traces → llm summarize → store facts). **this pattern maps to builder result consolidation.**

---

## problems

### structural problems
1. **runner is context-blind.** receives a script path, not the initiative's goal, criteria, constraints, or history. executes without knowing what success means. `gateway/builder_runner.py:~80` — no context injection.

2. **no result validation.** parses output but doesn't verify it against criteria. no self-consistency check, no review step, no retry with feedback.

3. **single-shot execution.** no iterative refinement, no retry, no sub-task decomposition. runs once, returns, done.

4. **no human-in-the-loop.** once enqueued, fully autonomous or fully nothing. no approval gates, no mid-execution feedback.

5. **initiative parser has no schema.** markdown with yaml frontmatter only. no pydantic validation, no structured initiative model, ambiguous error messages for malformed initiatives.

6. **status projection is flat.** doesn't aggregate queue items by initiative, can't report progress percentages or sub-task dags.

7. **builderpy.py is dead code.** facade adds zero behavior. all 5 components it wraps are importable directly.

8. **agent_runner presets are not wired to builder.** explorer/planner/coder/reviewer/researcher exist in `agent_runner.py` but builder_runner can't use them as sub-task types.

### test problems
9. **no test coverage.** no tests in `tests/` for any builder module. the state machine (6 states, repair loop, edge transitions) is entirely unverified by test.

---

## redesign — concrete api and schema

### phase 1 — strengthen foundation (kb-s2 queue + tests)

**1a. pydantic initiative model**

replace raw dict access in builder_initiative.py with validated model:

```python
from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime
from typing import Optional

class InitiativeStatus(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"  
    DONE = "done"
    FAILED = "failed"

class InitiativeCriteria(BaseModel):
    description: str
    validator: Optional[str] = None  # optional validation script path

class InitiativeApprovalGate(BaseModel):
    after_step: str  # step name or "all"
    requires: str  # "human" or "confidence>0.8"

class Initiative(BaseModel):
    id: str
    title: str
    goal: str
    criteria: list[InitiativeCriteria] = []
    constraints: list[str] = []
    approval_gates: list[InitiativeApprovalGate] = []
    retry_limit: int = 3
    timeout_minutes: int = 30
    metadata: dict = {}
```

**1b. state machine tests (kb-s2)**

every valid transition verified:
- pending → active (only when runner available)
- active → done (after successful validation)
- active → paused (manual or approval gate)
- paused → active (manual resume)
- active → abandoned (after retry limit exhausted)
- active → error_edge (unexpected failure)
- error_edge → active (manual retry)
- any → abandoned (manual cancel)

every invalid transition rejected:
- done → active, abandoned → pending, etc.

repair loop behavior: stalled item (active > timeout) → abandoned after 3 repair attempts.

**1c. remove builderpy.py.** delete the file. update any callers (none expected, the facade is dead code).

**migration path**: 2 weeks. add `gateway/models/builder.py` with pydantic models, write `tests/test_builder_queue.py` with 20+ transition tests, delete `builderpy.py`.

### phase 2 — runner redesign with context injection

**2a. RunnerContext — what the runner receives**

```python
from dataclasses import dataclass, field

@dataclass
class RunnerContext:
    """All context the runner needs to execute an initiative."""
    initiative: Initiative  # full pydantic model
    queue_item_id: str
    worktree_path: str
    history: list[RunnerResult] = field(default_factory=list)  # previous attempts
    sub_tasks: list[str] = field(default_factory=list)  # child queue item ids

@dataclass
class RunnerResult:
    attempt: int
    output: str
    validation: ValidationResult | None
    sub_tasks_spawned: list[str]
    duration_seconds: float
```

**2b. validation step**

after execution, runner validates output against criteria:

```python
class ValidationResult(BaseModel):
    passed: bool
    score: float  # 0.0 - 1.0
    failures: list[str] = []
    suggestions: list[str] = []

def validate_output(output: str, criteria: list[InitiativeCriteria]) -> ValidationResult:
    # llm-driven validation using a reviewer agent preset from agent_runner.py
    reviewer = spawn("reviewer", f"Validate this output against criteria: {json.dumps(criteria)}\n\nOutput: {output}")
    result = reviewer.wait(timeout=60)
    return parse_validation(result.output)
```

**2c. iterative refinement with retry**

```python
MAX_RETRIES = 3

async def run_with_retry(ctx: RunnerContext) -> RunnerResult:
    for attempt in range(1, ctx.initiative.retry_limit + 1):
        result = await run_single_shot(ctx)
        if result.validation and result.validation.passed:
            return result
        # inject validation failure into context for next attempt
        ctx.history.append(result)
    raise MaxRetriesExhausted(ctx.initiative.id, len(ctx.history))
```

**2d. sub-task spawning — builder DAG**

a builder initiative can declare sub-tasks. the runner spawns child queue items and blocks until they complete:

```python
async def execute_with_subtasks(ctx: RunnerContext) -> RunnerResult:
    children = []
    for task_def in ctx.initiative.sub_tasks:
        child = builder_queue.enqueue(
            initiative_id=task_def.initiative_id,
            parent_id=ctx.queue_item_id,
        )
        children.append(child)
    
    # wait for all children to complete (fan-out)
    results = await asyncio.gather(*[
        wait_for_completion(child.id) for child in children
    ])
    
    # merge results into parent output
    return merge_results(ctx, results)
```

**concurrency model**: sqlite queue table gets `parent_id` column (nullable, foreign key to self). builder_status.py aggregates by `parent_id IS NULL` for top-level initiatives and counts children by status. fan-out uses `asyncio.gather` — no distributed queue needed for local-first.

**2e. failure boundary — partial-result contract**

adopt context_assembler.py's pattern: sub-task failures produce warnings in the parent result, never crash the parent. the parent initiative decides whether warnings mean failure based on criteria.

### phase 3 — human-in-the-loop

**3a. approval gate schema**

initiatives declare gates inline:

```yaml
approval_gates:
  - after_step: "plan"
    requires: "human"
  - after_step: "implement"
    requires: "confidence>0.8"
```

**3b. approval flow**

1. runner hits approval gate → transitions item to `paused` with `approval_state = "awaiting_human"`
2. builder_status.py exposes `approval_required: true` for the item
3. ui shows approval prompt with intermediate results
4. user approves (`POST /builder/approve/{item_id}`) → item transitions to `active`, runner continues
5. user rejects with feedback (`POST /builder/reject/{item_id}` with `feedback` body) → item transitions to `active`, runner restarts with feedback as additional constraint

**3c. feedback integration**

rejection feedback is serialized as a `constraint` entry in the initiative model. on retry, the runner sees previous feedback as part of the goal context.

### phase 4 — initiative lifecycle

**4a. validation on submission**

`POST /builder/initiative` validates the initiative against the pydantic schema before enqueueing. returns 422 with field-level errors for invalid initiatives.

**4b. initiative templates**

pre-defined initiative yaml templates for common patterns stored in `.agents/initiatives/templates/`:
- `research-topic.yml`: research explorer → summarize planner
- `implement-feature.yml`: plan coder → implement coder → review reviewer
- `investigate-bug.yml`: explorer research → coder analyze → reviewer verify

**4c. scheduled initiatives**

cron-like scheduling in initiative frontmatter:

```yaml
schedule: "0 9 * * mon"  # every monday at 9am
schedule: "@daily"        # once per day
```

builder_loop.py gains a scheduler that checks for due scheduled initiatives and enqueues them.

### phase 5 — wire agent_runner presets to builder

the agent_runner.py presets (explorer, planner, coder, reviewer, researcher) are currently isolated from builder. wire them so agent runner presets become the execution engines for builder sub-tasks:

- builder initiative type "research" → spawns explorer + researcher agents
- builder initiative type "implement" → spawns planner + coder + reviewer pipeline
- builder initiative type "investigate" → spawns explorer + coder + reviewer pipeline

this reuses existing code rather than building new execution primitives.

---

## not recommended

- **real-time streaming of builder output.** poll-based status with detailed snapshots works for background tasks. streaming adds complexity without proportional value.
- **replacing sqlite queue with message broker.** sqlite is fast, local, and matches the local-first design. no deployment complexity.
- **making builderpy.py a real facade.** delete it. the individual components are importable directly.

---

## migration path (realistic timeline)

| week | deliverable |
|------|------------|
| 1-3 | pydantic initiative model + state machine tests (20+ transition tests) + delete builderpy.py |
| 4-6 | runner context injection + validation step + iterative refinement with retry |
| 7-8 | sub-task spawning with parent_id dag + builder_status aggregation |
| 9-10 | approval gates + human-in-the-loop ui |
| 11-12 | initiative schema validation + templates |
| 13-14 | scheduled initiatives + wire agent_runner presets |
| 15-16 | integration tests, documentation, ship kb-s2 |

range: 16 weeks for complete kb-s2 builder. phases are cumulative — each phase ships working code, not a branch that diverges for months.

---

## cross-references to other audit documents

- `architecture-honesty.md`: builder_queue.py is the most mature queue. builder_runner.py is pre-alpha. agent_runner.py presets are unused by builder. context_assembler.py's partial-result contract is the pattern for builder error handling.
- `repo-landscape.md`: skillopt's rollout→validate→edit→deploy loop informs phase 2. 12-factor-agents factor 7 (contact humans with tool calls) informs phase 3. agentevolver's self-questioning informs phase 4 templates.
- `kitty-vision-gap-analysis.md`: autonomous execution is a p1 gap. this redesign addresses it for builder tasks. chat-time autonomous execution (companion dispatches tasks during conversation) is a separate gap not covered here.
- `image-studio-character-system.md`: builder should be able to generate images as sub-tasks. the image job queue and builder queue are separate — consider a unified task queue or a bridge between them.