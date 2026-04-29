# Chat Log Consolidation Draft

## Source Files
- file: data/sessions/20260427_163926.json, 20260427_104140.json, 20260427_103839.json
- date range if known: 2026-04-27
- confidence: high (based on direct log content)

## Decisions
For each:
- title: Canadian-First Assistant Persona
- decision: Adopt a sharp, direct, budget-conscious, Canadian-sourced persona for the assistant.
- why: User engagement in logs suggests a preference for no-fluff, execution-oriented interaction.
- rejected alternatives: Generic polite assistant, theory-focused counselor.
- consequences: Responses will be more aggressive, brief, and focused on immediate financial/operational actions.
- source evidence: assistant messages in 20260427 sessions.
- status: accepted_candidate

## Parked Features
For each:
- title: Bank App Cash Flow Integration
- source/context: assistant messages suggesting bank app interaction.
- problem it solves: Automated financial leak detection and budget management.
- proposed behavior: Pull transaction data from bank apps (Shop.ca, Amazon.ca, Canadian Tire, etc.) and identify "nice to haves" to cut.
- why not now: Privacy/security implications and current focus on stabilization.
- dependencies: Secure bank API integration or manual paste logic.
- implementation sketch: Parser for bank transaction exports + classification engine.
- risks: Data privacy, API breakage.
- revival trigger: Core runtime stabilization complete.
- minimum safe version: Phase 7+
- status: parked_candidate

- title: Canadian Real Estate Analysis Engine
- source/context: assistant messages suggesting rental property analysis.
- problem it solves: Quick identification of high-cash-flow rental properties in Canadian cities.
- proposed behavior: Filter listings for cash flow > $1k/mo, vacancy < 5%, etc.
- why not now: Requires specialized data scraping/APIs and is outside core assistant focus.
- dependencies: MLS or similar real estate data source.
- implementation sketch: Scraper + financial calculator for real estate metrics.
- risks: Data accuracy, market volatility.
- revival trigger: Specialist domain expansion phase.
- minimum safe version: Phase 8+
- status: parked_candidate

## Active Tasks
For each:
- title: Install MLX-LM
- source: Assistant error messages in 20260427 sessions.
- next concrete action: run `pip install mlx-lm` in the environment.
- affected files: requirements.txt (verify if present)
- validation command: `python3 -c "import mlx_lm"`
- status: pending

- title: Fix Dead Socket.io Connection
- source: Assistant recommendation regarding `sYzrlwrRFthqlGpRAAAI`.
- next concrete action: Identify and remove dead socket.io polling logic for session `sYzrlwrRFthqlGpRAAAI`.
- affected files: src/api/socket_io.py (if exists), frontend interaction code.
- validation command: check logs for 400 errors on that session ID.
- status: pending

## Rejected Ideas
For each:
- idea: Generic "Theory-first" coaching.
- why rejected: Assistant persona shifted to "Execution-first" to avoid "spinning" and "brain fog".
- revisit trigger if any: User explicitly requests empathetic/soft support.

## Corrections
For each:
- correction: Remove `socket.io` logic for `sYzrlwrRFthqlGpRAAAI` from code.
- wrong behavior it prevents: Token waste and server crashes due to polling loop on dead session.
- affected files or surfaces: Socket connection manager.
- validation: Zero 400 errors for this session ID in logs.

## User Preferences
For each:
- preference: Direct, no-fluff communication style.
- evidence: "I hear the frustration... we skip the fluff and get straight to the gut."
- confidence: high
- scope: assistant persona

- preference: Canadian sourcing and budget focus.
- evidence: Multiple mentions of "$129/month", "Canadian-first", "Amazon.ca", "Canadian Tire".
- confidence: high
- scope: project goals

## Project Facts
For each:
- fact: Target price for Kitty service is $129/month.
- evidence: Assistant message: "I'm building a $129/month, Canadian-first AI assistant for your business right now."
- confidence: high

- fact: MLX local inference is currently failing due to missing `mlx-lm` package.
- evidence: Error logs in session `20260427_163926.json`.
- confidence: high

## File References
For each:
- path: data/sessions/
- why it matters: Contains raw chat logs for extraction.
- status: active

## Cleanup Candidates
For each:
- path: sYzrlwrRFthqlGpRAAAI
- type: logic / socket connection
- safe or unsafe: safe
- validation before cleanup: confirm session is truly dead.

## Specialist KB Candidates
For each:
- specialist: Audio Engineering Specialist (AU-7900 Amplifier repair)
- source material: Session 20260427 contents regarding fuse checking and transistor replacement.
- reason: Assistant demonstrated specific knowledge of amplifier troubleshooting.
- safety/source notes: High voltage/hardware safety warnings included.

## Skill Candidates
For each:
- skill: Budget Leak Finder
- trigger: "Where am I losing money?" or pasting transactions.
- behavior: Strip out "nice to haves" and find 3 leaks to close tonight.
- why not now if parked: Requires banking data privacy spec.

## Bugs / Failures
For each:
- symptom: [offline mode — OpenRouter/qwen/qwen3-8b:free unavailable; MLX local inference failed]
- likely cause: `mlx-lm` not installed; OpenRouter API rate limit or outage.
- affected files: model_loader.py, requirements.txt
- reproduction: run with local inference enabled without `mlx-lm`.
- validation after fix: Local inference starts without error.

## Open Loops
For each:
- question: Is the "Canadian-first" assistant persona a permanent shift or a specific test case?
- why it matters: Affects tone of all future responses.
- next step: Ask user for persona confirmation.

## Do Not Write Yet
- Any code related to automated bank login/scraping.
- Real estate investment calculation logic until core assistant is stable.
