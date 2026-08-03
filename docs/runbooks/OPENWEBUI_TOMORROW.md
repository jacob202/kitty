# Open WebUI tomorrow-ready runbook

This is an additive local shell for Kitty. It does not replace or delete the current Next.js UI, migrate historical data, or fork Open WebUI.

## One-time bootstrap

From the Kitty repository:

```bash
python3 scripts/openwebui_local.py bootstrap --accept-charges
```

The command:

- starts and verifies Kitty Gateway + LiteLLM;
- installs pinned Open WebUI `0.10.2` in an isolated Python 3.11 environment under `~/kitty-services/openwebui`;
- creates a fresh persistent data directory and persistent WebUI secret;
- points Open WebUI only at Kitty's `kitty-default` OpenAI-compatible model;
- disables Ollama discovery and persistent database overrides of the checked-in runtime configuration;
- starts Open WebUI on `127.0.0.1:3000`;
- performs one real SSE streaming smoke request (the `--accept-charges` flag is required because this can use provider credits);
- installs Gateway, LiteLLM, and Open WebUI as macOS login services only after the manual path passes;
- creates `~/Desktop/Kitty Chat.webloc` and opens the browser.

No historical Open WebUI directory is read, modified, or deleted.

## Daily use

Open **Kitty Chat** from the Desktop. The services should already be running after login.

```bash
python3 scripts/openwebui_local.py status
python3 scripts/openwebui_local.py doctor
python3 scripts/openwebui_local.py logs
```

Manual controls:

```bash
python3 scripts/openwebui_local.py up
python3 scripts/openwebui_local.py down
python3 scripts/openwebui_local.py open
python3 scripts/openwebui_local.py smoke --accept-charges
```

## Safe rollback

```bash
python3 scripts/openwebui_local.py uninstall-autostart
./kitty uninstall
./kitty
```

The last command starts the existing Kitty Next.js UI. Open WebUI data remains untouched at `~/kitty-services/openwebui/data-fresh`.

## Boundaries

- Local-only baseline: `127.0.0.1:3000`, authentication disabled for the fresh single-user instance.
- No historical data migration is attempted.
- No Open WebUI source is copied or modified.
- The Mac-local install and provider smoke must run on Jacob's Mac; repository tests cannot prove host credentials, launchd state, or provider availability.
