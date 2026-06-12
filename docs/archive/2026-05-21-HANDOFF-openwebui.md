# Kitty — Session Handoff (2026-05-21)

## What Got Done
- OpenWebUI integration Phases 1-5 (filter, docker terminal, code interpreter, workspace tools, actions)
- Architecture cleanup (deleted orphaned tools, wired import scripts into bootstrap/start_all)
- GITHUB_TOKEN renamed to GITHUB_PAT in .env (was shadowing gh keyring auth, causing 403 on push)
- Design system committed and pushed (40 files, 9820 insertions)
- 438 tests passing

## Current State
- All services STOPPED (gateway:8000, litellm:8001, openwebui:3001)
- 24 KBs exist in OpenWebUI, 1848 files linked, vector search WORKS (tested electronics KB)
- 90/92 remaining files failed to link (empty content / scanned PDFs with no extractable text)
- Council graph built (librarian -> specialist -> synthesizer via LangGraph) but NOT tested end-to-end yet
- search_client.py talks to OpenWebUI KB API — requires OpenWebUI running for council to work

## Key Files
- gateway/council_graph.py — LangGraph council (librarian, specialist, synthesis nodes)
- gateway/search_client.py — OWUI KB vector search client (singleton: search_client)
- gateway/domain_router.py — keyword classifier + specialist profiles
- gateway/mcp_council_server.py — MCP server exposing consult_council tool
- gateway/openwebui_filters/kitty_context_injector.py — inlet/outlet filter
- gateway/openwebui_library_tools/ — workspace tools (filesystem, knowledge search, memory search)
- gateway/actions/ — KB query, audio measurement, feeding schedule
- scripts/curation/assign_kb_files.py — classifies + links files to KBs
- kitty_gateway/openwebui.env — OWUI config (port, models, admin creds)

## Startup
1. bash gateway/start_litellm.sh (venv: ~/kitty-services/venv-litellm)
2. bash gateway/start_openwebui.sh (venv: ~/kitty-services/venv, port 3001)
3. bash gateway/start_gateway.sh (project venv, port 8000)
4. Or: bash gateway/start_all.sh

## Next Steps
1. Test council end-to-end (librarian routes query -> specialist searches KB -> synthesis)
2. Verify admin panel shows 6 prompts, 4 tools, 1 filter, 3 actions
3. Test chat context injection through the filter
4. Bulk ingest more books from ~/Documents/Books/ (only 1923 of ~1110 files uploaded; many scanned PDFs need OCR)
5. Fix empty-content files (90 failed) — likely need OCR pipeline for scanned PDFs

## Known Issues
- LiteLLM sometimes fails port 8001 bind (address in use) — kill stale processes first
- Many PDFs are scanned images with no extractable text — need vision/OCR ingestion path
- clinical & trauma KB has 0 files linked
- GITHUB_PAT (was GITHUB_TOKEN) is a fine-grained PAT with limited scope — gh keyring token handles push fine
