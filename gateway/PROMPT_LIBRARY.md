# Portable prompt / skill / tool bundle

**`kitty_openwebui_library.json`** holds **model-agnostic** prompts, skills, and tools (conversation steering, formats, research, handovers, etc.). It is **not** tied to Kitty internals or to a specific chat vendor—only the **import script filename** lives under `kitty_gateway/` because this repo uses it with Open WebUI’s API.

## What’s inside

- **`prompts`** — Short instructions you can inject mid-chat (ported under **CC BY 4.0** from [danielrosehill/OpenWebUI-Prompt-Library](https://github.com/danielrosehill/OpenWebUI-Prompt-Library); names here are generic).
- **`skills`** — Short markdown playbooks (structured reasoning, code review, research synthesis).
- **`tools`** — Python modules with **`class Tools`**: Wikipedia lookup (**MIT**, from [Haervwe/open-webui-tools](https://github.com/Haervwe/open-webui-tools)) and a tiny **stdlib** date/time helper.

`upstream` and per-prompt **Source** footers preserve license attribution.

## Local SQLite index (optional)

Rebuild a queryable copy under **`data/llm_library_index.db`** (schema: **`data/llm_library_index.schema.sql`**):

```bash
python3.12 scripts/build_llm_library_index.py
```

Tables: `prompts`, `skills`, `tools`, plus FTS5 `library_fts` (`kind`, `entry_key`, `title`, `body`). Example: `SELECT * FROM library_fts WHERE library_fts MATCH 'summary';`

## Import into Open WebUI (automated)

1. Open WebUI running; **`kitty_gateway/openwebui.env`** has `WEBUI_URL`, `WEBUI_ADMIN_EMAIL`, `WEBUI_ADMIN_PASSWORD`.
2. From the **kitty repo root**:

   ```bash
   ./venv/bin/python kitty_gateway/import_openwebui_prompts.py
   ```

3. Dry run (no auth):

   ```bash
   ./venv/bin/python kitty_gateway/import_openwebui_prompts.py --dry-run
   ```

Re-running is safe: existing **command** / **skill id** / **tool id** values are usually skipped.

## Legacy JSON

A file that is only a **list** of prompts still works: pass `--library` and only prompts are imported.

## Editing

- Edit **`kitty_openwebui_library.json`** and matching files under **`openwebui_library_tools/`**.
- Wikipedia tool needs packages from its frontmatter (`wikipedia-api`, plus `aiohttp` and `beautifulsoup4` as in upstream).

## Starter chips

Home-screen suggestions are separate: **`DEFAULT_PROMPT_SUGGESTIONS`** in **`kitty_gateway/openwebui.env`**.
