# Spec: Image Generator Fix

Date: 2026-04-30
Owner: Codex
Worker lane: Phase 4 Cleanup
Status: draft

## Goal

Adopt the isolated `src/tools/image_gen.py` diff from the parked MCP bundle branch. This fixes the Draw Things endpoint port (8080 -> 7859) and payload format to correctly support local image generation.

## Current App Boundary

Current runnable app:

`/Users/jacobbrizinski/Projects/kitty`

## Allowed Files

- `src/tools/image_gen.py`
- `specs/image-gen-fix.spec.md`

## Implementation Plan

1. Checkout `src/tools/image_gen.py` from `parked/mcp-agent-bundle-20260429`.
2. Ensure no regressions occur in the test suite.

## Smoke Test

Command:

```bash
/opt/homebrew/bin/python3.12 -c "import src.tools.image_gen"
```

Expected result: No syntax errors.
