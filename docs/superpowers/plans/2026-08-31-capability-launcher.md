# Capability Launcher Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a live capability launcher that exposes Kitty-owned surfaces and installed Skills through Cmd-K.

**Architecture:** Add one read-only catalog route that projects core destinations plus Skill Registry metadata. Add deterministic explicit-skill resolution in context assembly. Consume the catalog in the existing CommandPalette and delegate launch behavior to page.tsx so the palette never becomes an execution authority.

**Tech Stack:** FastAPI/Pydantic, Python Skill Registry/context assembler, Next.js/React, cmdk, Vitest/Testing Library, pytest.

**Spec:** `docs/superpowers/specs/2026-08-31-capability-launcher.md`

## Global Constraints
- Never mutate the canonical dirty checkout.
- Do not create a second capability, action, skill, project, Builder, or automation authority.
- TDD: each behavior gets a failing test before production code.
- Preserve current Cmd-K search and recent-chat behavior.

---

### Task 1: Capability catalog route
**Files:** Create `gateway/routes/capabilities.py`; modify `gateway/routes/register.py`; create `tests/test_capabilities_route.py`.
**Interfaces:** Produces `GET /capabilities -> {capabilities: Capability[]}` where each item has `id,label,description,category,launch` and optional `view`/`skill_name`.
- [ ] Write route test asserting core destinations plus a discovered Skill and no skill `content` leakage.
- [ ] Run focused pytest and verify RED because route is absent.
- [ ] Implement minimal typed read-only catalog and register router.
- [ ] Run focused pytest and verify GREEN.
- [ ] Commit Task 1.

### Task 2: Explicit Skill activation
**Files:** Modify `gateway/context_assembler.py`; modify/create focused context-assembler test.
**Interfaces:** `Use skill: <installed-name>` resolves exactly through `skill_registry.get/invoke`; unknown names fall back without fabricated skill content.
- [ ] Write failing test for exact explicit skill selection.
- [ ] Run focused pytest and verify RED.
- [ ] Implement deterministic directive parsing and prompt injection.
- [ ] Run focused pytest and verify GREEN.
- [ ] Commit Task 2.

### Task 3: Capability-first Cmd-K
**Files:** Modify `gateway/kitty-chat/src/lib/gateway.ts`, `gateway/kitty-chat/src/components/CommandPalette.tsx`, `gateway/kitty-chat/src/app/page.tsx`, `gateway/kitty-chat/tests/CommandPalette.test.tsx`.
**Interfaces:** `fetchCapabilities()` returns the catalog; `CommandPalette` receives `onLaunchCapability(capability)`; page routes views or composes `Use skill: <name>\n\n` in Chat.
- [ ] Add failing Vitest coverage for displayed capability metadata, view launch, and Skill launch callback.
- [ ] Run focused Vitest and verify RED.
- [ ] Implement client types/fetch, capability loading/rendering, and page launch behavior.
- [ ] Run focused Vitest and verify GREEN.
- [ ] Run TypeScript build and relevant backend/frontend regression tests.
- [ ] Commit Task 3.
