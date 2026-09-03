# Kitty — local-first AI companion (macOS)
- Runtime: Python 3.12 (FastAPI gateway) + TypeScript (Next.js native UI); LiteLLM proxy for model routing.
- Layout: `gateway/` (backend + `gateway/kitty-chat/` UI), `tests/`, `docs/`. Runtime data under `data/` and logs under `logs/` are not source.
- For current branch, phase, session state, and next action, use live evidence: `git status --short --branch`, the Global Agent Room (`workspace_global`), and Builder projections — not this file.
