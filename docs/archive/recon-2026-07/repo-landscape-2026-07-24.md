# repo landscape: 2026-07-24

> **position in the kit**: inventory of external code and products. feeds into `kitty-vision-gap-analysis.md` (what others do that we don't), `kittybuilder-redesign.md` (execution patterns to steal), and `image-studio-character-system.md` (image generation analogues).

survey of external projects organized by relevance to kitty's four pillars: companion identity, autonomous execution, image generation, and local-first infrastructure.

---

## direct competitors — local-first ai companions

these are projects that share kitty's core claim: a personal ai companion running on your machine with memory and persistence.

### companion-emergence (hanamorix)
- github.com/hanamorix/companion-emergence — 27 stars, python + tauri desktop app
- local-first emotional companion with persistent supervisor (launchd/systemd/task scheduler). 16 emotional avatar registers, memory store with hebbian connections, dreaming at night, soul crystallizations across sessions, creative voice fingerprint.
- runs against claude via cli. ollama provider ships but is less tuned.
- **kitty overlap**: the closest project to kitty's companion vision. emotional state model, persistence model (brain runs even when desktop app is closed), memory consolidation via dreaming — all patterns kitty should study.
- **where kitty leads**: companion-emergence has no builder, no image generation, no skill registry, no context assembler across 9 stores. it is a companion but not an executor.

### somora_agent (thenaxon)
- github.com/thenaxon/somora_agent — 8 stars, typescript local-first gateway
- multi-agent runtime with persistent memory across claude/codex/ollama. three-layer memory model (inbox per agent → shared obsidian wiki → read-only vault). 40+ tools across 12 toolsets. tui + web + mobile pwa clients.
- three-phase dream consolidation: rem extraction → deep consolidation → lucid cleanup.
- **kitty overlap**: memory model (inbox → wiki → vault) maps to kitty's memory_class → consolidation → weave. multi-engine switching (claude ↔ codex ↔ ollama mid-conversation) is something kitty's llm_client.py could absorb.
- **where kitty leads**: somora has no builder, no image generation, no 9-store memory graph, no companion personality policy layer.

### bolly (triangle-int)
- github.com/triangle-int/bolly — 9 stars, rust + sveltekit desktop
- ai companion with soul.md (editable by the companion itself), persistent memory (bm25 + vector), mood system, heartbeat autonomy (wakes every 45 minutes), scheduled check-ins, 50+ tools, mcp extensibility.
- single binary deployment. self-hosted, byok (bring your own key).
- **kitty overlap**: soul.md + mood system resemble what kitty needs for companion personality. heartbeat autonomy (waking on its own to check in) is a concrete implementation of proactive behavior.
- **where kitty leads**: bolly has no builder, no image generation, no context assembler across heterogeneous stores, no memory policy for sensitive content.

### other companions (less mature or different scope)
- **aico** (boeni-industries) — 10 stars, python + flutter. emotion simulation + agency + scheduler. lmdb + chromadb memory. planned multi-device sync.
- **koda** (heykodaai) — 0 stars, python + react. voice-first local companion. claude sonnet brain. local stt/tts (kokoro + whisper). open source preview stage.
- **thoth** (haraldh/siddsachar) — 0 stars, python desktop. full local via ollama (39 curated models). 5 messaging channels. langgraph reAct agent. obsidian-compatible knowledge graph.
- **jarvis** (bionorthtech) — 3 stars, python + tauri. fully local via lm studio + chromadb. 4-level autonomy system with internal drives and emotions. 5 scheduled bots for maintenance tasks.

---

## autonomous execution — self-evolving agents and builder patterns

### skillopt (microsoft)
- github.com/microsoft/SkillOpt — python, mit license. published june 2026.
- **treats a skill document as the trainable state of a frozen agent.** loop: rollout evidence → optimizer reflection → bounded edits → held-out validation gate → deploy `best_skill.md`. text-space learning rate prevents destructive rewrites. rejected-edit buffer as negative feedback.
- ships with claude code, codex, copilot, and devin integration. v0.2 includes skillopt-sleep (nightly offline self-evolution for local coding agents).
- results: +23.5 points on gpt-5.5 across 6 benchmarks. skills transfer across model scales and between codex and claude code harnesses.
- **kitty overlap**: **this is the single most relevant external project.** kitty's builder_initiative.py parses initiative manifests — skillopt shows how those initiatives could self-improve through rollout → validate → edit cycles. the `best_skill.md` artifact maps to kitty's skill_registry.py output. skillopt-sleep maps to kitty's memory_consolidation.py nightly_dream.
- **concrete idea**: kitty's builder_runner.py could run skillopt's training loop against builder initiatives. each initiative becomes a trainable skill document stored in `.agents/skills/`.

### 12-factor agents (humanlayer)
- github.com/humanlayer/12-factor-agents — 23.5k stars, typescript design guide
- **principles for production-grade llm applications**, not a framework. endorsed by andrej karpathy ("context engineering, not prompt engineering") and shopify ceo tobi lutke.
- 12 factors: natural language to tool calls, own your prompts, own your context window, tools are structured outputs, unify execution and business state, launch/pause/resume, contact humans with tool calls, own your control flow, compact errors into context, small focused agents, trigger from anywhere, stateless reducer.
- scaffold: `npx create-12-factor-agent` demonstrates all principles in <200 lines of typescript.
- **kitty overlap**: factors 3 (own your context window), 7 (contact humans with tool calls), 8 (own your control flow), and 12 (stateless reducer) directly apply to builder_runner.py redesign. factor 3 maps to context_assembler.py. factor 7 maps to human-in-the-loop approval gates.

### agentevolver (modelscope)
- github.com/modelscope/AgentEvolver — 1.5k stars, python, apache 2.0
- end-to-end self-evolving agent training: self-questioning (automatic task generation), self-navigating (experience-guided exploration), self-attributing (attribution-based credit assignment).
- rl-based policy optimization with grpo. service-oriented dataflow architecture.
- **kitty overlap**: the self-questioning mechanism (autonomously creating diverse tasks) maps to builder_initiative.py template generation. self-navigating (summarizing cross-task experience) maps to memory_consolidation.py cluster summarization.

### autoskill (ecnu-icalk)
- github.com/ecnu-icalk/autoskill — python
- experience-driven lifelong learning: extracts skills from real conversations, merges and versions them, reuses across sessions. skillbank stores versioned skill.md files. offline extraction from archived conversations.
- ships with autoskill4doc (document-to-skill), autoskill4openclaw (trajectory-driven), skillevo (replay → evaluate → mutate → promote).
- **kitty overlap**: autoskill's skill extraction from conversation history maps to kitty's consolidation pipeline. the versioned skill store pattern validates kitty's skill_registry approach.

### agent0 (aiming-lab)
- github.com/aiming-lab/Agent0 — 1.2k stars, python, apache 2.0
- self-evolving agents from zero data: curriculum agent proposes frontier tasks, executor agent learns to solve them via tools. +18% on math, +24% on general reasoning. zero external data required.
- vision-language variant (agent0-vl) adds +12.5% on visual reasoning.
- **kitty overlap**: curriculum agent + executor agent pair maps to builder_initiative.py (task proposal) + builder_runner.py (task execution). self-play improvement cycle without human data.

### sloth-ai (dhruvb26)
- github.com/dhruvb26/sloth-ai — autonomous productivity platform
- agents monitor gmail, slack, linear, and take action without user prompts. orchestrator coordinates 9 specialized agents via mastra + claude opus 4.5. demo flow: deployment failure detected → investigates vercel logs + slack → creates linear ticket → writes code fix → commits to github → notifies team.
- **kitty overlap**: the signal-driven autonomous action model (monitor sources → detect events → investigate → act) maps to kitty's signal_store.py + builder pattern. the 9-agent architecture validates kitty's agent_runner.py multi-preset design.

### gaunt-sloth (pukeko-robotics)
- github.com/pukeko-robotics/gaunt-sloth — cli ai assistant for ci/cd
- configuration-driven cli with pr review, diff q&a, interactive chat/code. supports a2a protocol for agent-to-agent communication. all prompts are editable markdown files. connects to mcp servers including oauth.
- **kitty overlap**: the a2a protocol support (connecting to other agents) is a pattern for kitty's builder when it needs to consult external tool agents. the "all prompts editable markdown" pattern matches kitty's skill_registry markdown approach.

---

## research and tool-calling patterns

### gpt-researcher (assafelovic)
- github.com/assafelovic/gpt-researcher — autonomous web research agent
- sub-query decomposition, parallel search, source aggregation, report generation.
- **kitty overlap**: sub-query decomposition strategy directly applicable to builder initiative planning and agent_runner.py researcher preset.

### pr-agent (codium-ai)
- github.com/codium-ai/pr-agent — pr review automation
- tool-calling discipline: describe tool, validate result, retry with context. code-aware context window management.
- **kitty overlap**: tool validation + retry pattern for builder_runner.py result validation step and agent_runner.py tool execution.

### mastra
- github.com/mastra-framework/mastra — typescript agent framework
- agents, tools, workflows, memory. used by sloth-ai as orchestrator.
- **kitty overlap**: kitty's gateway/llm_client.py fills this role in python. mastra validates the pattern but is not a direct dependency.

---

## prompt engineering and system design

### system prompts — canonical collections
- **x1xhlol/system-prompts-and-models-of-ai-tools** — 142k stars. the definitive collection. 45+ agent system prompts extracted including claude code (4 agents, verified 85-95% against leaked source), cursor, windsurf, devin, cline, bolt, manus, v0, replit. updated july 2026.
- **mabue777/system-prompts-reference** — organized by category: chatbots, coding agents, app builders, platform integrations, tool definitions, voice modes, personalities, safety, api internals, patterns and analysis. most architecturally useful for studying prompt design patterns.
- **dontriskit/awesome-ai-system-prompts** — 6k stars. includes clawdbot's modular approach (soul.md / agents.md / identity.md) with three-tier approval flow and context-dependent privacy rules. this modular pattern is directly applicable to kitty's companion personality design.

### clawdbot modular prompt architecture
- personality/voice in soul.md, operational rules in agents.md, identity/privacy in identity.md
- three-tier approval: do without asking / get approval / never do
- context-dependent privacy rules for messaging platforms
- **kitty overlap**: this is the clearest pattern for kitty's missing companion personality system. currently kitty has a single system prompt. splitting into soul.md (personality), agents.md (rules), and identity.md (privacy boundaries) would give the companion persistent, editable, composable character.

### modular context obsidian plugin (klemensgc)
- llm knowledge base as sources → wiki → schema (karpathy-aligned). 25 google workspace mcp tools. multi-terminal split layouts (up to 8 sessions).
- **kitty overlap**: the vault-as-context pattern (sources → wiki → schema) validates kitty's memory approach of raw stores → assembled context. the multi-terminal approach is a ui pattern for kitty's builder observing multiple concurrent agents.

### fabrics (daniel miessler)
- github.com/danielmiessler/fabric — cli pattern library
- curated prompt patterns for content processing. local-first, markdown-based, extensible.
- **kitty overlap**: the explicit pattern directory concept maps to kitty's `.agents/skills/` directory. kitty's skills are implicit today — adopting fabric's explicit pattern structure would make them composable.

---

## frameworks kitty should not adopt but should learn from

### dspy (stanford)
- programming llms via declarative modules. compile-time prompt optimization. not a runtime agent.
- **verdict**: the signature-based validation concept is useful but dspy's serialization overhead and python 3.12 friction make it a poor direct dependency for kitty.

### llama index
- massive surface area for indexing, retrieval, query engines.
- **verdict**: kitty's sqlite + chromadb + mem0 + custom weave is lighter and purpose-built. llama index would add weight without proportional value.

### onlook
- visual react component editor. no agent capabilities.
- **verdict**: not relevant to kitty's current scope.

---

## kitty's position in the landscape

| dimension | kitty | companion-emergence | somora | bolly | sloth-ai | skillopt |
|-----------|-------|---------------------|--------|-------|----------|----------|
| local-first | yes | yes | yes | yes | partial | training only |
| companion identity | yes | yes | multi-agent | yes | no | no |
| autonomous execution | yes (builder) | no | no | heartbeat only | yes (9-agent) | skill training |
| image generation | yes | no | no | no | no | no |
| memory persistence | yes (9 stores) | yes | yes (3 layers) | yes | yes | no |
| self-evolving skills | no | no | no | no | no | yes |
| context assembler | yes (deep) | no | no | no | no | no |
| production readiness | pre-1.0 | pre-1.0 | pre-1.0 | pre-1.0 | demo | research paper |
| ui | next.js | tauri | tui+web+pwa | sveltekit | web | cli + webui |

**kitty's unique advantage**: no other project combines companion identity + autonomous builder execution + image generation + 9-store memory graph + context assembler with privacy gates. the individual pieces exist elsewhere but the integration is unique.

**kitty's unique weakness**: skillopt, agentevolver, and autoskill demonstrate that the field is moving toward self-evolving skills. kitty has the infrastructure (builder queue, agent runner, skill registry, consolidation pipeline) to build self-evolving skills but hasn't wired them together yet. this is the highest-leverage gap in the landscape.

---

## cross-references to other audit documents

- `kitty-vision-gap-analysis.md`: the "self-evolving skills" gap is not yet listed — skillopt and autoskill show it should be p1
- `kittybuilder-redesign.md`: skillopt's rollout→validate→edit→deploy loop maps to builder runner redesign phase 2
- `architecture-honesty.md`: the memory infrastructure to support self-evolving skills already exists (9 stores, consolidation pipeline, nightly_dream)
- `image-studio-character-system.md`: no external project combines character-consistent image gen with companion identity — kitty's integration is novel

---

## research gaps — what was not surveyed

- closed-source products (chatgpt, claude, gemini, grok as products — surveyed only their system prompts architecturally)
- mobile-first companions (replika, character.ai, n同龄)
- enterprise agent platforms (salesforce agentforce, servicenow ai agents)
- voice-only companions (not in scope for kitty's current phase)
- video generation tools (out of scope for image studio v2)