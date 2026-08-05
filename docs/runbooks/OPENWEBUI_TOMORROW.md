# Open WebUI tomorrow-ready runbook

This is an additive local shell for Kitty. It does not replace or delete the current Next.js UI, migrate historical data, or fork Open WebUI. Open WebUI is the replaceable interface; Kitty Gateway remains authoritative for model routing, providers, memory, projects, Tutor, tools, and Builder state.

## One-time bootstrap

From the Kitty repository:

```bash
python3 scripts/openwebui_local.py bootstrap --accept-charges
```

The command:

- starts and verifies Kitty Gateway + LiteLLM;
- installs pinned Open WebUI `0.10.2` in an isolated Python 3.11 environment under `~/kitty-services/openwebui`;
- creates a persistent owner-only data directory and WebUI secret;
- binds the unauthenticated single-user shell only to `127.0.0.1:3000`;
- points Open WebUI only at Kitty Gateway and prevents ambient provider keys from leaking into the WebUI process;
- disables Ollama discovery, telemetry, community sharing, update checks, arena models, and persistent database overrides of checked-in runtime configuration;
- configures the truthful Kitty model menu: Auto, Fast, Think, Code, and Vision;
- creates or repairs the five workspace agents: Daily Kitty, Research, Coding, Tutor, and Builder Operator;
- attaches only Kitty's bounded tool server to the agents that require tools;
- proves Gateway discovery, the configured agents, tool registration, memory search, notes search, projects, calendar, Tutor contract, and read-only Builder projection;
- performs bounded live model turns only after the explicit `--accept-charges` authorization;
- installs Gateway, LiteLLM, and Open WebUI as macOS login services only after the manual path passes;
- creates `~/Desktop/Kitty Chat.webloc` and opens the browser.

No historical Open WebUI directory is read, modified, or deleted.

## Acceptance verification

Run the read-only configuration and feature checks at any time:

```bash
python3 scripts/openwebui_local.py verify
```

Before calling the setup fully proven, run the bounded live route checks too:

```bash
python3 scripts/openwebui_local.py verify --accept-charges
```

The paid verification sends one small non-streaming turn through each advertised model route and one end-to-end turn through Daily Kitty. It fails loudly if a configured model, agent, tool surface, or required Kitty projection is unavailable. An unavailable calendar connection or an empty project list is reported distinctly instead of being mistaken for a broken endpoint.

## Daily use

Open **Kitty Chat** from the Desktop. The services should already be running after login.

```bash
python3 scripts/openwebui_local.py status
python3 scripts/openwebui_local.py doctor
python3 scripts/openwebui_local.py verify
python3 scripts/openwebui_local.py logs
```

Manual controls:

```bash
python3 scripts/openwebui_local.py up
python3 scripts/openwebui_local.py down
python3 scripts/openwebui_local.py open
python3 scripts/openwebui_local.py smoke --accept-charges
```

`doctor` is the fast service-health check. `verify` is the broader feature acceptance check. Neither command silently repairs or invents successful state.

## Backup, restore, and rollback

```bash
python3 scripts/openwebui_local.py backup
python3 scripts/openwebui_local.py down
python3 scripts/openwebui_local.py restore
python3 scripts/openwebui_local.py rollback
```

Backups use SQLite's backup API, are validated before publication, and include the persistent WebUI secret when present. Restore refuses to run while the service is active, validates the source, creates a pre-restore backup, and atomically replaces the database. Rollback returns the desktop shortcut to the canonical Kitty Next.js UI and leaves Open WebUI data untouched.

## Boundaries

- Local-only baseline: `127.0.0.1:3000`, authentication disabled for the fresh single-user instance.
- No historical data migration is attempted.
- No Open WebUI source is copied or modified.
- Builder access from Open WebUI is read-only.
- The Mac-local install, launchd state, credentials, and live provider routes must be verified on Jacob's Mac; repository CI cannot prove host-specific runtime state.