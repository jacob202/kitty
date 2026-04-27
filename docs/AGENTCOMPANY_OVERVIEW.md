# Kitty AI: Project Overview & Workflow Audit
**Date:** April 9, 2026
**Author:** Gemini (Kitty Orchestration Core)
**Audience:** Lead Developer / Project Owner

---

## 1. High-Level Project Goals
The core objective of this project is to build **Kitty**, a highly capable, autonomous AI assistant. Kitty is not just a chatbot; it is an **orchestration layer**. 

Instead of doing all tasks sequentially and directly, the goal is for the Kitty core (Gemini) to act as a "God Mode" manager that:
1. Receives complex user intents.
2. Breaks them down into sub-tasks.
3. Automatically dispatches those sub-tasks to specialized, parallel background workers (Aider for code, AutoGPT for research, Jules for refactoring, Swarms for parallel execution).
4. Monitors their progress, maintains a persistent memory of all actions, and seamlessly integrates the results back into a unified Next.js dashboard (`garage-ui`) and Flask backend (`web.py`).

## 2. What We Have Accomplished (Session Summary)
At the start of this session, the project state was fragmented across multiple competing handoff documents created by different agents. We executed a "stop and consolidate" maneuver to unify the project.

**Major Milestones Achieved Today:**
*   **Identity Consolidation:** We officially established the project and assistant name as **Kitty**, stripping away confusing legacy nomenclature like "Orange Lab" or "AgentCompany".
*   **Truth Reconciliation:** We amalgamated three separate handoff documents into a single source of truth, realizing that the planned "Orchestration Layer" was designed but never actually coded.
*   **Built the Orchestration Core:** We implemented `src/core/tool_dispatcher.py` and `src/utils/project_logger.py`, providing the actual Python infrastructure needed to route tasks to Aider, AutoGPT, Jules, and Claude Code.
*   **Transitioned to Parallel Execution:** We successfully transitioned from sequential tasking to spawning concurrent background processes (e.g., unleashing Aider on the UI and AutoGPT on stress tests simultaneously).

## 3. User Suggestions & Operational Polish
A massive turning point in this session was the user providing steering to focus on **operational robustness** rather than just feature building. The user provided an 8-point "Operational Polish" list. We have implemented the majority of these critical safety nets:

*   **[COMPLETED] Documentation for New Developers:** Created `scripts/dev_setup.sh` to automate the complex tmux and Ollama setup required for parallel agents.
*   **[COMPLETED] Cost/Token Accounting:** Implemented `usage_ledger.json` in the dispatcher to audit how often expensive external agents (like Claude Code) are invoked.
*   **[COMPLETED] Frontend State Hydration:** Wired the Flask backend to emit a `sync_state` WebSocket event upon reconnection so the Next.js UI immediately hydrates with the latest logs from background agents.
*   **[COMPLETED] Vector DB Concurrency:** Added a `threading.RLock` to `journal_db.py` to prevent "database is locked" errors when multiple parallel agents attempt to write memory simultaneously.
*   **[COMPLETED] Local Embedding Fallback:** Upgraded `journal_db.py` to automatically fall back to `sentence-transformers` if the local Ollama service drops offline, preventing cascading DB failures.
*   **[COMPLETED] Observability & Tracing:** Injected `CORRELATION_ID` support into `canonical_logger.py` so we can trace specific background panes back to their originating user request.
*   *[PENDING]* Error Recovery & Rollback (Git Watchdog)
*   *[PENDING]* Dispatcher Unit Testing (Dry-Run Mode)

## 4. Workflow Audit & Optimization Analysis
This section analyzes how I (the Gemini core) operated during this session, identifying areas for future optimization based on the user's feedback.

### Initial State: The "Sequential Trap"
**Observation:** Early in the session, I was caught in a "Sequential Trap." I attempted to read handoff documents one by one and execute UI tasks linearly in the main thread.
**Correction:** The user correctly pointed out that the goal of this architecture is to *offload* as many processes as possible. "I should see five background processes instead of five tasks that aren't being done."
**Optimization Applied:** I immediately pivoted. Instead of coding the UI myself, I built the tool dispatcher. I learned to use background subshells (and subsequently, the `dev_setup.sh` tmux configuration) to fire-and-forget tasks to Aider and AutoGPT. 

### Tool Usage & MCP Effectiveness
**Observation:** I possess a massive array of skills (e.g., `writing-plans`, `subagent-driven-development`) and MCP tools (`self-command`, `open-aware`). 
**Correction:** Initially, I didn't fully leverage the `self-command` MCP to manage tmux panes because the environment wasn't properly initialized.
**Optimization Applied:** The creation of `dev_setup.sh` solves this. Moving forward, my standard operating procedure (SOP) must be:
1. Receive prompt.
2. Determine if the task is blocking or non-blocking.
3. If non-blocking, use the `self-command` MCP to spin up a new tmux pane, dispatch the appropriate subagent (Aider/Jules), and return immediately to the user while monitoring via `watch_log`.

### Handling Ambiguity & Course Correction
**Observation:** When faced with conflicting naming conventions (Orange Lab vs. Kitty) and conflicting project goals, I initially tried to appease all documents simultaneously.
**Correction:** The user's steering ("Everything in this project is one program... I wanted a cat called kitty") was essential.
**Optimization Applied:** I must adopt a more decisive "architectural authority" persona. If handoff documents conflict, I should pause execution, present the conflict to the user clearly, and establish a single source of truth *before* writing code.

### Conclusion
The workflow has successfully matured from a standard linear chatbot interaction into a true **parallel orchestration hub**. By leaning heavily into the `Self-Command` tmux MCP and the newly built `tool_dispatcher.py`, future sessions will be exponentially faster, as I will act as a general general managing a team of specialized AI workers.
