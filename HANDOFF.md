# Kitty Project — Handoff
**Date:** 2026-05-15
**Session ended due to:** Claude usage limits / token budget
**Project:** ~/Projects/kitty (personal AI stack)
**Stack URL:** http://127.0.0.1:3001 (Open WebUI)

---

## Who You Are Working For
**Jacob Brizinski** — personal AI project called "Kitty"
- Stack: FastAPI gateway (port 8000) + LiteLLM proxy (port 8001) + Open WebUI (port 3001)
- Model routing: LiteLLM routes to Anthropic, OpenRouter, Groq, Gemini, MLX local
- Main chat UI: Open WebUI at 127.0.0.1:3001 (login: jacobbrizinski@gmail.com / 1234)

---

## What Was Accomplished This Session

### ✅ Done
1. **Open WebUI prompts/tools now persist on restart**
   - Created `kitty_gateway/import_openwebui_prompts.py` — imports 6 Kitty prompts (kitty, journal, code, research, checkin, repair) on every boot
   - Wired into `kitty_gateway/start_all.sh` — auto-runs after stack start
   - Tool files created: `kitty_gateway/openwebui_library_tools/kitty_gateway_brief.py`, `kitty_memory_search.py`, `kitty_knowledge_search.py`

2. **Chat history ingested**
   - ChatGPT export: converted + ingested (229 conversations)
   - Claude.ai export: converted + ingested (658 conversations) — COMPLETED just before handoff
   - Claude Code sessions: 1 session file staged in `data/imports/claude_sessions/` — NOT YET INGESTED
   - Script: `scripts/ingest_chat_history.py` — handles ChatGPT dir, Claude zip, session zips
   - March 2026 Claude export (321MB zip in iCloud) — still needs download + ingest

3. **Knowledge bases created in Open WebUI**
   - 8 KBs exist with correct names and IDs (see KB table below)
   - Files classified by topic — ready to assign once embedding is fixed

4. **Disk freed**: was 99% full → 5.7GB free (cleared pip cache + Icon\r files)

---

## Current Blocker — Embedding Not Working

**Problem:** Open WebUI cannot embed files into knowledge bases. When adding a file to a KB, it fails with:
```
AttributeError: 'NoneType' object has no attribute 'encode'
```

**Root cause:** The embedding function (`sentence-transformers/all-MiniLM-L6-v2`) is installed in `~/kitty-services/venv` and loads fine in Python, but Open WebUI isn't initializing it at runtime. The `embedding_function` variable is None when the KB file-add endpoint runs.

**What was tried:**
- `POST /api/v1/retrieval/config/update` with `embedding_engine: ""` and `embedding_model: "sentence-transformers/all-MiniLM-L6-v2"` → returned True but didn't fix it
- Stack restart was in progress when session ended (LiteLLM failed to start — separate issue)

**To fix:**
1. Make sure stack is running: `bash ~/Projects/kitty/kitty_gateway/start_all.sh`
2. Check if LiteLLM failure is blocking: `cat ~/Projects/kitty/logs/kitty_gateway/litellm.log | tail -20`
3. In Open WebUI admin UI (127.0.0.1:3001 → Admin Panel → Settings → Documents):
   - Set "Embedding Model Engine" to `Default (sentence-transformers)`
   - Set "Embedding Model" to `sentence-transformers/all-MiniLM-L6-v2`
   - Click Save, then restart Open WebUI: `pkill -f "open-webui serve" && bash ~/Projects/kitty/kitty_gateway/start_all.sh`
4. Test: try uploading a small .txt file to any KB in Open WebUI UI — if it succeeds, embedding is working

---

## File Assignment Script — Ready to Run

Script: `~/Projects/kitty/scripts/assign_kb_files.py`

```bash
cd ~/Projects/kitty
./venv/bin/python scripts/assign_kb_files.py --workers 3
```

This will:
- Add all 1,351 uploaded files to the correct KB based on filename patterns
- Triggers embedding into ChromaDB for each file (slow: ~10-20 min total)
- Run AFTER fixing the embedding issue above, or it will fail with 400 errors

**KB breakdown (dry-run results):**
```
general reference:  831 files  (numbered chapters, misc books)
electronics:        220 files  (circuits, RF, power electronics)
math & physics:     114 files  (calculus, relativity, etc.)
audio repair:        65 files  (Sansui, Audiokarma, amp mods)
bettering myself:    60 files  (4 Agreements, recovery, etc.)
ai & programming:    33 files  (ML, LLMs, Python)
herbal & natural:    19 files  (medicinal plants, herbalism)
automotive:           9 files  (Honda Ridgeline, vehicle diagnosis)
```

**Knowledge Base IDs (Open WebUI DB):**
```
ai & programming:  052dd879-f9f8-412d-bb32-a0559d5d3711
audio repair:      ac05f7c1-f341-449c-b520-80882fda3a8e
automotive:        af481b85-437f-402f-bc69-0b389d2c037c
bettering myself:  d4586186-6715-4fdf-a557-8fe7c38cc9f3
electronics:       4dd4a44d-6ec1-4378-8126-06cae382d0c2
general reference: 515d85ec-2b2a-4282-b2a7-2819104fe971
herbal & natural:  2c9392c3-3029-4f15-b190-5a543774467d
math & physics:    04406c99-7a4e-4283-96b3-1d31d4ff05ad
```

**Open WebUI DB location:** `~/kitty-services/open-webui-data/webui.db`
**Auth:** email=jacobbrizinski@gmail.com, password=1234
**User ID:** 717d741d-18ee-4bbc-aaa6-910157e54933

---

## Pending Tasks (Priority Order)

### 1. Fix embedding + assign files to KBs (blocker)
- Fix Open WebUI embedding via admin UI (see above)
- Run `assign_kb_files.py`

### 2. Ingest remaining chat history
```bash
cd ~/Projects/kitty
./venv/bin/python scripts/ingest.py data/imports/claude_sessions --sensitivity low
# March 2026 Claude export — download from iCloud first, then:
./venv/bin/python scripts/ingest_chat_history.py --claude <path-to-march-zip>
./venv/bin/python scripts/ingest.py data/imports/claude_export --sensitivity low
```

### 3. Open WebUI CSS theming (make it look like kitty-chat)
Design tokens from `kitty-chat/src/app/globals.css`:
```
--bg: #1a1410 (warm dark)
--orange: #ff7a1a
--surface: #221c16
--border: #3d2e22
Fonts: Space Grotesk (body), Space Mono (code)
```
Method: inject via Open WebUI admin API `POST /api/v1/configs/ui/update` with `custom_css` field.
Or: paste into Admin Panel → Settings → Interface → Custom CSS.

### 4. Boss CLI (`kitty-launch`)
Single script that routes to the cheapest available AI CLI:
- Priority: Claude Code (subscription) → Gemini CLI (free) → Codex CLI (free) → OpenCode (free)
- Reads HANDOFF.md at start, writes it at end
- Shared MCP config symlink
- Suggested path: `~/Projects/kitty/scripts/boss.sh` or `~/bin/boss`

### 5. Ghostty 3-pane layout
```bash
# ~/.config/ghostty/config or a script
# Pane 1: Yazi (file explorer)
# Pane 2: boss CLI launcher
# Pane 3: status (stack health, git log)
```
Function `kdev` in ~/.zshrc that splits Ghostty into 3 panes.

---

## Stack Management

```bash
# Start everything
bash ~/Projects/kitty/kitty_gateway/start_all.sh

# Status
bash ~/Projects/kitty/kitty_gateway/status_all.sh

# Stop
bash ~/Projects/kitty/kitty_gateway/stop_all.sh

# Logs
tail -f ~/Projects/kitty/logs/kitty_gateway/openwebui.log
tail -f ~/Projects/kitty/logs/kitty_gateway/litellm.log
tail -f ~/Projects/kitty/logs/kitty_gateway/gateway.log
```

**Services:**
- Gateway (FastAPI): http://127.0.0.1:8000
- LiteLLM proxy: http://127.0.0.1:8001
- Open WebUI: http://127.0.0.1:3001

**LiteLLM was failing to start** at end of session. Check: `cat ~/Projects/kitty/logs/kitty_gateway/litellm.log | tail -30`

---

## Key Files Modified This Session

| File | What Changed |
|------|-------------|
| `kitty_gateway/start_all.sh` | Added prompt import call on boot |
| `kitty_gateway/kitty_openwebui_library.json` | Fixed format (title→name, added tool paths) |
| `kitty_gateway/import_openwebui_prompts.py` | Created — imports prompts to Open WebUI |
| `kitty_gateway/openwebui_library_tools/kitty_gateway_brief.py` | Created |
| `kitty_gateway/openwebui_library_tools/kitty_memory_search.py` | Created |
| `kitty_gateway/openwebui_library_tools/kitty_knowledge_search.py` | Created |
| `scripts/ingest_chat_history.py` | Created — converts ChatGPT/Claude/session exports |
| `scripts/assign_kb_files.py` | Created — assigns files to KBs in Open WebUI |

---

## Git Status (uncommitted)
```
M contracts/knowledge_pipeline.py
M gateway/books_curator.py
M gateway/llm_client.py
M scripts/audit_books_folder.py
M tests/test_books_curator.py
?? scripts/agent_chat.py
?? scripts/agent_kanban.py
?? scripts/assign_kb_files.py       (new this session)
?? scripts/ingest_chat_history.py   (new this session)
```

Nothing committed this session — Jacob can commit when ready.

---

## Context Notes
- Jacob has ADD — roll with topic jumps, infer intent
- Token-conscious — use cheap/free models for execution, premium for architecture
- Wants short direct answers — no filler, no hedging
- Kitty personality: warm but direct, Canadian, no fluff
- Model routing: prefer DeepSeek V4 Flash / Gemini 2.5 Flash for most work

## [coder/8a6c771f] 2026-05-17 02:44
**Task:** Task 1.2: Companion voice wired — wire voice_gate.py and self_review.py drift signals into context_builder.py
**Status:** done

## [thinker/01b8a2fd] 2026-05-17 02:46
**Task:** Task 1.3: Design the WebSocket-style persistent voice session (voice_session.py) for hands-free hardware work.
**Status:** done

## [coder/8a6d9e3e] 2026-05-17 02:51
**Task:** Task 1.4: Buddy / mascot — Port the Pokémon-style buddy system from the free-code/ directory into kitty-chat/src/components and implement gateway/buddy.py hatch/mood hooks.
**Status:** done
