# Repository Guidelines

## Project Structure & Module Organization

Kitty is a local-first personal AI assistant centered on a Python FastAPI gateway and a Next.js chat UI. Core backend code lives in `gateway/`, with routes in `gateway/routes/`, service utilities in `gateway/lib/`, and launch helpers around `./kitty`. The primary web UI is `gateway/kitty-chat/`; treat older UI directories as non-canonical unless current docs say otherwise. Tests live in `tests/`; product and architecture notes live in `docs/`. Runtime data and logs belong under `data/` and `logs/` and should not be committed.

## Build, Test, and Development Commands

- `./kitty install`: install local launchd services for the gateway and LiteLLM.
- `./kitty start`: start Kitty services.
- `./kitty status`: show service status and health.
- `./kitty doctor --json`: run operational checks and report warnings/failures.
- `python3.12 -m pytest tests/ -q --tb=short`: run the default Python test slice.
- `cd gateway/kitty-chat && npm run dev`: run the chat UI on `127.0.0.1:4000`.
- `cd gateway/kitty-chat && npm run build`: verify the production UI build.
- `cd gateway/kitty-chat && npm test`: run Vitest frontend tests.

## Coding Style & Naming Conventions

Follow surrounding style before introducing new patterns. Python uses 4-space indentation, typed helpers where useful, and small route/service functions with explicit error handling. TypeScript/React uses functional components, clear prop names, and colocated helpers under `src/`. Name Python tests `test_*.py`; place React tests near the feature they cover. Keep comments rare and explanatory.

## Testing Guidelines

Pytest is configured in `pytest.ini`; the default run excludes slow browser, merge-gate, and integration markers. Use targeted tests while developing, then run the default suite before pushing. For UI changes, run `npm test` and `npm run build` in `gateway/kitty-chat/`. If you touch launch, auth, ports, or env loading, also run `./kitty status` and `./kitty doctor --json`.

## Commit & Pull Request Guidelines

Recent history uses conventional-style subjects such as `fix(phase-a): ...`, `test(doctor): ...`, and `chore(phase-a): ...`. Keep commits focused on one concern. PRs should explain the user-facing change, list verification, mention skipped checks, and link related roadmap or issue context. Include screenshots or recordings for visible UI changes.

## Security & Configuration Tips

Never print or commit `.env` values, API keys, launchd secrets, `data/`, or local logs. Gateway auth should fail closed when secrets are missing. Treat localhost as exposed to other local processes; preserve bearer-token checks and host validation when changing routes.
