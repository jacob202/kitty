# Council Routing — Design & Spec (v1)

> Source of truth for this spec: the provided Council configuration block.
> Repository integration points are marked `[ASSUMPTION]` and must be verified
> against the actual `gateway/` codebase before implementation.

## 1. Purpose
The Council is a **supervisor**, not an executor. Per the config it follows a
fixed loop: **ANALYZE → PRIORITIZE → ROUTE → VERIFY**. It turns one user message
into one or more *tasks*, decides which are trivial enough to handle inline, and
dispatches the rest to a specialist *agent*.

## 2. Vocabulary
- **Task** — a single unit of work decomposed from user input.
- **Route / Dispatch** — the assignment of a task to a specific agent.
- **Agent** — a specialist executor. Config names three roles:
  - `DeepSeek` → Logic / Code
  - `Claude` → Synthesis / Planning
  - `Ollama` → CLI / Routine
- **Task Dispatch Format** — the JSON envelope that carries a task to its agent
  (see §5). It is the contract between the Council and every agent.

## 3. Task Classification (ANALYZE + ROUTE)
Config defines three categories: **Coding, Research, Writing**.

**v1 classifier — rule-based heuristics (deterministic, zero-latency):**
| Signal | Category |
|--------|----------|
| code keywords (implement, bug, refactor, test, function, PR) | Coding → DeepSeek |
| research/find/summarize/compare/investigate | Research → Claude |
| write/draft/doc/explain/plan | Writing → Claude |
| CLI/shell/cron/run/execute locally | Routine → Ollama |

Ambiguous or mixed input → default to `Claude` (synthesis) for a triage pass.

**v2 (deferred):** LLM-based classifier for nuance. Adds latency/cost; not in v1.

## 4. Triviality Gate (PRIORITIZE)
If a task is low-complexity AND single-category (e.g. "list files", "what port is
the gateway on?"), the Council executes it inline and skips dispatch. This keeps
the agent roster free for real work. Heuristic: no decomposition needed + matches
a known trivial pattern → inline.

## 5. Dispatch Contract (Task Dispatch Format)
```json
{
  "task_id": "uuid",
  "priority": "high | medium | low",
  "assigned_to": "agent_name",
  "context": {
    "project": "name",
    "docs": ["path"],
    "state": "summary"
  },
  "instructions": "Direct, actionable task."
}
```
This envelope is the **only** thing an agent receives — keep it self-contained.

## 6. Routing Logic (pseudo-code)
```python
def council_route(user_input: str, state: State) -> list[Result]:
    tasks = decompose(user_input)              # ANALYZE
    results = []
    for task in tasks:
        if is_trivial(task):                   # PRIORITIZE
            results.append(execute_inline(task))
            continue
        agent = classify_and_select(task)      # ROUTE
        dispatch = TaskDispatch(
            task_id=uuid(), priority=task.priority,
            assigned_to=agent, context=build_context(state),
            instructions=task.instructions,
        )
        results.append(run_agent(dispatch))    # ROUTE
    return verify(results)                     # VERIFY
```

## 7. VERIFY Step
Quality gate applied to every agent result before display:
- non-empty / no error markers / no silent fallback (aligns with repo Prime
  Directive: *fail loud, never mask*).
- on failure → re-dispatch to a fallback agent or surface the raw error.

## 8. Agent Registry & Backend `[ASSUMPTION]`
The config names `DeepSeek / Claude / Ollama` as agents, but the repo already has
a model-router (`AgentRouter` + LiteLLM, OpenAI-compatible). Two integration
options — define an `AgentBackend` interface so either works:
- **(A)** Map each Council agent role onto the existing `AgentRouter` model map.
- **(B)** Call the named external agents directly (separate endpoints/creds).

> OPEN DECISION — needs your confirmation (you didn't answer this earlier):
> does the Council dispatch to the **existing AgentRouter/LiteLLM** stack, or to
> **separate external agents** (DeepSeek/Claude/Ollama as standalone services)?

## 9. Placement `[ASSUMPTION]`
Proposed: new `gateway/council.py` exposing a `council_route()` entrypoint, wired
behind a `/council` route or a `./kitty council ...` CLI. Reuses `gateway/paths.py`
and the existing `State`/handoff machinery.

## 10. Out of Scope (v1)
- Kitty Tutor RAG (separate feature; becomes one routed task type later).
- Multi-agent debate / parallel orchestration.
- Persistent task queue (use KittyBuilder queue if needed later).

## 11. Open Questions
1. Agent backends: AgentRouter vs external agents? (§8)
2. Council entrypoint: HTTP route, CLI, or both? (§9)
3. Does `state` in the dispatch context mean `.claude/STATE.md` summary, or a
   runtime object? Keep v1 to a short text summary.
