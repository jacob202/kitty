# Kitty ↔ Open WebUI prompt library

Saved prompts (slash commands) are defined in **`kitty_prompt_library.json`**. Titles and intent are tied to **repo file names** you already use (`docs/ARCHITECTURE.md`, `gateway/context_builder.py`, `config/SOUL.md`, …) so prompts stay aligned with the codebase.

## Import (automated)

1. Ensure Open WebUI is up and `kitty_gateway/openwebui.env` has `WEBUI_URL`, `WEBUI_ADMIN_EMAIL`, `WEBUI_ADMIN_PASSWORD` (same as `import_openwebui_functions.sh`).
2. From the **kitty repo root**:

   ```bash
   ./venv/bin/python kitty_gateway/import_openwebui_prompts.py
   ```

3. Dry run (no POST):

   ```bash
   ./venv/bin/python kitty_gateway/import_openwebui_prompts.py --dry-run
   ```

If a **command** already exists, the API returns “command taken” and the script **skips** that row (safe to re-run).

## Import (manual)

Open WebUI → **Workspace** → **Prompts** → **Import** (if your build supports JSON import), or create prompts by hand using the `command`, `name`, and `content` fields from `kitty_prompt_library.json`.

## Starter cards (`DEFAULT_PROMPT_SUGGESTIONS`)

Home-screen suggestion chips are separate from the prompt library list; they live in **`kitty_gateway/openwebui.env`** as `DEFAULT_PROMPT_SUGGESTIONS`. You can add Kitty-oriented starters there (JSON array) without duplicating every slash command.

## Editing the library

- Add or change entries in **`kitty_prompt_library.json`** (valid JSON list).
- Re-run the import script; existing commands are skipped until you rename `command` or delete the old prompt in the WebUI.
