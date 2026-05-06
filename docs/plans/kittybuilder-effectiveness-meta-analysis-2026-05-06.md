# KittyBuilder Effectiveness Meta-Analysis

Date: 2026-05-06
Status: approved direction, not yet implemented
Scope: KittyBuilder orchestration, context engineering, agent routing, and token incentives

## Executive Summary

The next KittyBuilder improvement should not be "more agents" or "cheaper agents first." The stronger architecture is:

`Jacob brain dump -> Intent Compiler -> Work Contract -> Context Pack -> Execution Router -> Evidence Ledger -> Learning Loop`

The missing layer is a compiler that converts unstructured human intent into a precise, scoped, testable build contract before any worker starts. This should maximize effectiveness per token, not raw efficiency.

## Updated Incentive

The correct optimization target is:

`lowest expected verified cost`

This includes:

- LLM tokens
- retries
- failed tests
- bad code cleanup
- misalignment with the request
- human time spent re-explaining
- quality loss from underpowered workers

Cheap output that causes rework is expensive. A premium model or stronger context pack is justified when it reduces expected rework.

## Research Findings

### 1. Multi-agent work is useful, but not by default

Anthropic's multi-agent research system showed strong gains for broad research tasks, but also reported that multi-agent systems can burn about 15x more tokens than normal chat. Their own guidance says multi-agent systems fit tasks with heavy parallelism, many tools, and more information than one context window can hold.

Implication for KittyBuilder:

- Use parallel agents for independent research, audits, and disjoint implementation slices.
- Do not use a swarm for tightly coupled coding tasks.
- Every delegated lane needs objective, output format, allowed tools, sources, and boundaries.

Source:
- https://www.anthropic.com/engineering/multi-agent-research-system

### 2. Context engineering is the main reliability problem

LangChain's agent docs frame real-world agent failure as usually one of two causes: the model is not capable enough, or the right context was not passed. They emphasize controlling model context, tool context, and lifecycle context.

Implication for KittyBuilder:

- Build a Context Compiler that selects, compresses, and orders context.
- Stop passing broad summaries or whole prior chats to workers by default.
- Keep static, cacheable instructions stable and separate from variable task data.

Source:
- https://docs.langchain.com/oss/python/langchain/context-engineering

### 3. Long context is not the same as good context

The "Lost in the Middle" paper shows that long-context models can underuse relevant information buried in the middle of large prompts. Performance is often strongest when important information is near the beginning or end.

Implication for KittyBuilder:

- Do not solve drift by dumping more context.
- Put invariant rules and task objective early.
- Put acceptance criteria and "stop conditions" late as a final checklist.
- Keep unrelated background out of worker prompts.

Source:
- https://huggingface.co/papers/2307.03172

### 4. Tool design is as important as model choice

SWE-agent's Agent-Computer Interface work shows that agents improve when their tools are shaped for model use. Their notes emphasize model-friendly file viewers, concise search output, edit-time linting, and explicit success output when commands produce no text.

Implication for KittyBuilder:

- Do not expose broad shell access when a narrow tool works.
- Make worker tools return concise, predictable, parseable output.
- Add deterministic middleware before/after model calls.
- Prefer "run approved validation command" over "run whatever tests seem relevant."

Source:
- https://github.com/SWE-agent/SWE-agent/blob/main/docs/background/aci.md

### 5. Existing OSS should be reused selectively

Relevant projects:

- Aider: strong git-aware coding loop, codebase map, lint/test integration, local/cloud models.
- Promptfoo: prompt and agent eval regression testing.
- BMad Method: useful planning workflow concepts and readiness gates.
- Open SWE: useful reference architecture for sandboxing, AGENTS.md context, subagents, middleware, and async invocation.
- OpenHands: useful large reference, likely too heavy to absorb now.
- DSPy/TextGrad: useful later for prompt optimization after KittyBuilder has eval data.

Recommendation:

- Reuse Aider concepts or adapter path for execution.
- Adopt Promptfoo for brain-dump-to-contract regression tests.
- Borrow BMad readiness gates and document flow.
- Treat Open SWE/OpenHands as references, not dependencies, until KittyBuilder's own control loop is stable.

Sources:
- https://github.com/Aider-AI/aider
- https://github.com/promptfoo/promptfoo
- https://github.com/bmad-code-org/BMAD-METHOD/blob/main/docs/reference/workflow-map.md
- https://github.com/langchain-ai/open-swe
- https://github.com/All-Hands-AI/OpenHands
- https://dspy.ai/
- https://textgrad.com/

### 6. Prompt caching requires prompt layout discipline

OpenAI prompt caching benefits exact prefix matches. Static content should appear first, while variable task data should come later.

Implication for KittyBuilder:

- Put system rules, schema, and stable role instructions first.
- Put variable brain dump, selected files, and run state later.
- Avoid changing static prompt text on every run.
- Hash and version prompt templates.

Source:
- https://developers.openai.com/api/docs/guides/prompt-caching

### 7. Security and permissions are not optional

OWASP LLM06 identifies excessive agency as a major LLM application risk. Root causes include excessive functionality, excessive permissions, and excessive autonomy.

Implication for KittyBuilder:

- Workers should get the least tool permission needed.
- Broad shell/fetch/write tools need explicit mode gates.
- Privileged operations require user approval or approved spec.
- Worker outputs are untrusted until verified.

Source:
- https://genai.owasp.org/llmrisk/llm062025-excessive-agency/

## What We Were Missing

### Missing Layer 1: Intent Compiler

Jacob often provides valuable but messy brain dumps. The system should preserve that raw input, then compile it into a precise Builder Brief.

The compiler should output:

- raw_input
- normalized_goal
- non_goals
- success_criteria
- validation_commands
- allowed_files_or_areas
- forbidden_work
- assumptions
- ambiguities
- blocking_question
- context_targets
- risk_level
- recommended_execution_mode
- handoff_prompt

If confidence is low, ask one concrete question. If confidence is high, proceed with a compiled contract.

### Missing Layer 2: Context Compiler

After the work contract exists, KittyBuilder should generate a minimal context pack.

Context pack rules:

- Include only task-relevant authority docs.
- Include exact file snippets, not whole files, when possible.
- Put invariant instructions first.
- Put task-specific data last.
- Include acceptance gates at both top and bottom.
- Include source paths for every claim.

### Missing Layer 3: Execution Router

Routing should be based on expected verified cost.

Inputs:

- task complexity
- risk level
- coupling level
- available health of worker CLIs/providers
- context length
- expected failure cost
- historical pass/fail data

Modes:

- answer_only
- intake_only
- scout
- single_worker
- parallel_workers
- review_gate
- human_question

### Missing Layer 4: Worker Health Preflight

Before routing work, KittyBuilder should know which workers actually function.

Signals:

- binary present
- auth present when detectable
- version/help command works
- previous run status
- common failure mode
- cooldown or disabled flag

This avoids dispatching to broken providers.

### Missing Layer 5: Evidence Ledger

Every run should leave machine-readable evidence:

- run_id
- raw_input_hash
- compiled_contract_path
- context_pack_path
- model/worker used
- files read
- files changed
- commands run
- tests passed/failed
- tokens/cost when available
- outcome
- residual risks
- next action

This makes optimization possible and prevents false completion claims.

### Missing Layer 6: Prompt/Workflow Evals

The brain-dump compiler and routing policies need regression tests.

Use cases:

- messy brain dump with multiple goals
- request that conflicts with forbidden work
- request that should ask one question
- request that should become one spec
- request that should run review-only
- request that should not parallelize

Promptfoo is the likely first tool because it is local, open source, and designed for prompt/model comparisons and regressions.

## Novel Operating Model

KittyBuilder should behave like:

1. Compiler
   - Transforms informal intent into strict work contracts.

2. Scientific lab
   - Every run produces evidence, metrics, and learning.

3. Execution market
   - Workers are selected by expected verified cost, not static preference.

4. Courtroom
   - Completion claims require evidence.

5. Immune system
   - Risky tools/actions are scoped, gated, and reversible.

This is the stronger path than a generic autonomous swarm.

## Recommendation

Do not replace KittyBuilder with OpenHands/Open SWE yet.

First build:

1. Intent Compiler
2. Context Compiler
3. Worker Health Preflight
4. Evidence Ledger
5. Promptfoo regression suite

Then evaluate whether Aider, Open SWE, or a custom executor should become the main execution backend.

## Practical Acceptance Criteria For The Next Phase

The next phase is successful when:

- A messy Jacob brain dump compiles into a deterministic work contract.
- The compiler asks one blocking question when needed.
- The context pack is smaller than the raw prior-session context.
- KittyBuilder refuses to route to unhealthy workers.
- Every execution recommendation says why it chose the mode.
- Every worker run writes an evidence ledger row.
- Promptfoo or equivalent evals catch regression in compiler output quality.
- The system improves effectiveness per token, not just token count.

