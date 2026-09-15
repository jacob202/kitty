# Artifact Canvas Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a safe reusable artifact preview canvas beginning in Library.

**Architecture:** Add an artifact-id-only content route backed by ArtifactStore and an explicit safe media allowlist. Add a reusable frontend ArtifactCanvas that fetches text content or embeds image/PDF content, then mount it from Library without changing ArtifactStore authority.

**Tech Stack:** FastAPI/Starlette FileResponse, ArtifactStore, React/Next.js, react-markdown, remark-gfm, Vitest/Testing Library, pytest.

**Spec:** `docs/superpowers/specs/2026-08-31-artifact-canvas.md`

## Global Constraints
- Work only in the isolated Wave 2 worktree.
- ArtifactStore remains the only artifact identity/source metadata authority.
- No arbitrary path parameter crosses the browser boundary.
- No HTML/SVG active-content rendering in this slice.
- TDD for each behavior.

---

### Task 1: Safe artifact content route
**Files:** Modify `gateway/routes/artifacts.py`; modify `tests/test_artifacts_routes.py`.
**Interfaces:** `GET /artifacts/{artifact_id}/content` returns registered ready bytes for allowlisted preview media.
- [ ] Write failing tests for text content, missing backing file, non-ready state, and unsupported HTML.
- [ ] Run focused pytest and verify RED.
- [ ] Implement artifact-id lookup, state/path checks, media allowlist, and FileResponse.
- [ ] Run focused pytest and verify GREEN.
- [ ] Commit Task 1.

### Task 2: Reusable Artifact Canvas
**Files:** Create `gateway/kitty-chat/src/components/artifacts/ArtifactCanvas.tsx`; modify `gateway/kitty-chat/src/lib/gateway.ts`; modify `gateway/kitty-chat/tests/LibraryView.test.tsx`.
**Interfaces:** `artifactContentUrl(id)` and `fetchArtifactText(id)`; canvas accepts artifact, mobile state, close callback, and optional use-in-chat action.
- [ ] Add failing Library tests proving Markdown opens and renders and the canvas closes.
- [ ] Run focused Vitest and verify RED.
- [ ] Implement safe text/image/PDF renderers and explicit unsupported state.
- [ ] Run focused Vitest and verify GREEN.
- [ ] Commit Task 2.

### Task 3: Library integration and verification
**Files:** Modify `gateway/kitty-chat/src/components/LibraryView.tsx` and focused tests.
**Interfaces:** Ready previewable rows expose Open; selected artifact mounts ArtifactCanvas; existing image chat action remains unchanged.
- [ ] Add/extend tests for image preview URL, PDF preview, mobile canvas, and disabled unsupported preview.
- [ ] Run tests and verify RED where behavior is missing.
- [ ] Implement minimal row/canvas integration.
- [ ] Run backend/frontend focused suites, Ruff, `git diff --check`, and production Next build.
- [ ] Commit and publish stacked PR against Wave 1 branch.
