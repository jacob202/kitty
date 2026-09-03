# Kitty feature reality — 2026-07-28

This document separates implemented capability from integrated daily-use experience.

| Area | Implemented capability | Current product reality |
|---|---|---|
| Chat and context | Gateway context assembly, durable chats, projects, memory evidence, model aliases | Functional but fragile; provider selection and recovered-thread state required repair |
| Tutor | RAG ingestion, grounded teaching, deterministic grading, spaced repetition, mastery gates, quizzes, HTTP routes, CLI, and UI panel | Real subsystem, not a complete curriculum authoring platform; discovery and onboarding are weak |
| Image generation | MCP server with Gemini/Nano Banana, Imagen, DALL-E, ComfyUI and Draw Things; editing, references, characters, refinement loops; basic UI | Real backend and a basic surface, but engine setup and identity-preserving workflows are not yet a polished Image Lab |
| KittyBuilder | Durable SQLite queue, leases, fencing, attempts, recovery, initiatives, worker/reviewer execution, PR metadata, status/control UI | Substantial orchestration backend; not a conversational coding agent and not yet a smooth mission-to-merged-PR product |
| Work | Tasks and todos | Previously split from Builder by implementation domain; now consolidated into one Work surface |

## Correct interpretation

Kitty is not empty scaffolding. It has several real, tested subsystems. The failure is product integration: capabilities were built in parallel, surfaced inconsistently, and documented through stale snapshots. Preserve the tested engines; replace or simplify the shell and wiring where dogfooding proves they fail.

A missing path in a web index is not evidence that a subsystem does not exist. Reviews must inspect current `main`, search renamed paths, and distinguish backend capability from an end-to-end supported workflow before recommending deletion.

## Foundation history

Open WebUI was previously the intended commodity chat shell with Kitty layered above it. The repository deliberately removed that integration in June 2026 and made `kitty-chat` the sole frontend. That was an architectural choice, not proof that the earlier approach was imaginary or inherently invalid. Future foundation decisions must compare working candidates while preserving Kitty-owned context, memory, projects, permissions, routing, Tutor, Image Lab, and KittyBuilder capabilities.

## Hard rule

No public or canonical document may call a feature shipped merely because backend code exists. Use these states:

- **Working:** Jacob can complete the intended workflow through the supported UI.
- **Partial:** meaningful code exists, but setup, integration, or UX blocks normal use.
- **Planned:** no end-to-end usable implementation.
