# High-Level Roadmap: The Leverage Path

| Phase | Milestone | Success Metric | Current Status |
| :--- | :--- | :--- | :--- |
| **1. Workbench** | Autonomous "Plan-Test-Fix" loop (D-0017) | 10+ turn autonomy without "continue" | 🏗️ Implementation |
| **2. Mentorship** | Socratic Knowledge Gates & analogy training | Jacob passes 1st Knowledge Gate | 📅 Queued |
| **3. Memory** | Semantic JournalDB (Pure MLX, no Ollama) | Zero-Ollama embedding latency | 📅 Queued |
| **4. Taste** | Knowledge Curation (Superseded theory detection) | 0% pollution from outdated data | 🏗️ Implementation |
| **5. Hands** | MCP Integration (System Control) | Kitty can read/edit local Mac files | 📅 Queued |
| **6. Value** | First "External Tool" built autonomously | Validated solution for non-Jacob user | 📅 Queued |

## Immediate Executable Chunks (Phase 1)

### Chunk 1.1: Autonomy Infrastructure
- [ ] Implement `max_iters=10` default in chat.
- [ ] Implement `reasoning_content` visibility (Thinking tokens).
- [ ] Register `compile_builder_request` as a primary tool.

### Chunk 1.2: The Critique Logic
- [ ] Update Intent Compiler to use reasoning model (R1/O1).
- [ ] Force mandatory "Boring Path" recommendation in Brief.
- [ ] Add approval gate blocking code until "Go" or "Approved."

### Chunk 1.3: Socratic Layer
- [ ] Create `USER_LEVEL.json` to track absorption.
- [ ] Add 3-sentence constraint to all educational output.
- [ ] Trigger first "Knowledge Gate" after 3 tool calls.
