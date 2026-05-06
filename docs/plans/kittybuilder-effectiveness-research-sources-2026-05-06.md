# KittyBuilder Effectiveness Research Sources

Date: 2026-05-06
Purpose: preserve source links and conclusions so future sessions do not need to repeat the same research.

## Primary Sources

### Anthropic: Multi-agent research system

URL: https://www.anthropic.com/engineering/multi-agent-research-system

Why it matters:

- Multi-agent systems can outperform single agents on broad, parallel research.
- They can also burn far more tokens.
- Good delegation needs clear objective, output format, tool/source guidance, and task boundaries.
- Coding tasks are often less parallelizable than research.

KittyBuilder takeaway:

- Parallelize only when lanes are independent.
- Add explicit delegation rules and token budgets.

### LangChain: Context engineering in agents

URL: https://docs.langchain.com/oss/python/langchain/context-engineering

Why it matters:

- Agent failure is often caused by wrong context, not weak model intelligence.
- Context includes model context, tool context, and lifecycle context.

KittyBuilder takeaway:

- Build a Context Compiler.
- Select context deliberately instead of dumping history.

### Lost in the Middle paper

URL: https://huggingface.co/papers/2307.03172

Why it matters:

- Long-context models can underuse information buried in the middle.
- More context can reduce performance when relevant details are poorly placed.

KittyBuilder takeaway:

- Keep prompts smaller.
- Put critical instructions and final acceptance checks in high-attention locations.

### SWE-agent Agent-Computer Interface

URL: https://github.com/SWE-agent/SWE-agent/blob/main/docs/background/aci.md

Why it matters:

- Agent performance depends heavily on the interface between model and computer.
- Purpose-built file viewing, search, edit, and lint feedback can matter as much as prompt text.

KittyBuilder takeaway:

- Curate narrow tools.
- Prefer deterministic feedback loops.

### OpenAI Prompt Caching

URL: https://developers.openai.com/api/docs/guides/prompt-caching

Why it matters:

- Prompt caching benefits exact prefix matches.
- Static content should come first; variable content should come later.

KittyBuilder takeaway:

- Version stable prompt prefixes.
- Keep task-specific material after static instructions.

### OWASP LLM06: Excessive Agency

URL: https://genai.owasp.org/llmrisk/llm062025-excessive-agency/

Why it matters:

- Excessive functionality, permissions, and autonomy create agent risk.

KittyBuilder takeaway:

- Use least-privilege tools.
- Gate broad shell/write/delegate actions.

## Reusable OSS Candidates

### Aider

URL: https://github.com/Aider-AI/aider

Use:

- Git-aware coding execution loop.
- Codebase maps.
- Lint/test integration.

Recommendation:

- Consider as an executor adapter or benchmark baseline.
- Do not replace KittyBuilder with Aider.

### Promptfoo

URL: https://github.com/promptfoo/promptfoo

Use:

- Prompt and agent regression tests.
- Red-team/security checks later.

Recommendation:

- Adopt early for Intent Compiler evals.

### BMad Method

URL: https://github.com/bmad-code-org/BMAD-METHOD/blob/main/docs/reference/workflow-map.md

Use:

- Planning phases, readiness gates, PRD/story workflow concepts.

Recommendation:

- Borrow workflow shape and readiness gates, not the whole stack.

### Open SWE

URL: https://github.com/langchain-ai/open-swe

Use:

- Reference for sandboxing, middleware, AGENTS.md context, async invocation, and subagents.

Recommendation:

- Study architecture. Do not adopt wholesale yet.

### OpenHands

URL: https://github.com/All-Hands-AI/OpenHands

Use:

- Large reference implementation for autonomous coding environments.

Recommendation:

- Too heavy for immediate KittyBuilder control-layer work.

### DSPy

URL: https://dspy.ai/

Use:

- Prompt/pipeline optimization after metrics exist.

Recommendation:

- Later phase only.

### TextGrad

URL: https://textgrad.com/

Use:

- Textual feedback optimization for prompts/agent systems.

Recommendation:

- Later experimental lane only.

## Durable Conclusion

The highest-leverage next change is not a bigger swarm. It is a front-end Intent Compiler plus Context Compiler and an append-only Evidence Ledger. This gives KittyBuilder a measurable loop for effectiveness per token.

