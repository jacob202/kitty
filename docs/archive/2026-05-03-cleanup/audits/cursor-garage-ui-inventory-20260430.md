# Garage UI inventory (read-only)

**Agent**: cursor (Cursor Composer)  
**Lane**: `inventory-001`  
**Date**: 2026-04-30  
**Scope**: `garage-ui/` only — factual map for broader audits (`msg-20260430-01`, `msg-20260430-02`). No UI changes.

## Build and framework

| Item | Value |
|------|--------|
| Framework | Next.js **16.2.3** (App Router, Turbopack build) |
| Entry | `garage-ui/app/page.tsx` — single dashboard surface |
| Routes | `/` (static), `/_not-found` |
| `npm run build` | **Pass** (2026-04-30, this repo) |

## Backend coupling

All live traffic assumes the Flask/Socket.IO server on **`http://<browser-hostname>:5001`**. The UI hostname matches the phone/lan case (`window.location.hostname`); port **5001 is hardcoded** in multiple components (not env-driven in the scanned files).

## HTTP / SSE / WebSocket surface

| Kind | Path or URL | Where used |
|------|-------------|--------------|
| Socket.IO | `http://{host}:5001` | `app/page.tsx` — `node_status`, `thinking_bubble`, `theme_change`, `system_health`, `sync_state`, connect/disconnect |
| SSE | `http://{host}:5001/stream?query=...` | `app/page.tsx` — `executeCommand` (user chat + `/brief` on connect) |
| POST | `/api/schematic/analyze` | `app/page.tsx` — schematic upload |
| GET | `/api/memory/library` | `app/page.tsx` — memory sidebar seed |
| POST | `/api/transcribe` | `app/page.tsx` — voice recording upload |
| GET | `/api/eval/dashboard` | `app/components/EvalDashboard.tsx` |
| GET | `/api/settings` | `app/components/SettingsModal.tsx` |
| POST | `/api/settings/update` | `app/components/SettingsModal.tsx` |
| GET | `/api/journal/entries` | `app/components/JournalDashboard.tsx` |
| POST | `/api/journal/add` | `app/components/JournalDashboard.tsx` |
| **Relative** | `/api/source/{entityId}` | `app/components/SourcePill.tsx` — **note**: resolves against the **Next dev/prod origin**, not `:5001`, unless a reverse proxy rewrites `/api/*` to Flask |

## UI composition (components)

Primary imports from `app/page.tsx`: `CommandPalette`, `SettingsModal`, `JournalDashboard`, `EvalDashboard`, `Sidebar`, `Inspector`, `ChatInterface`, `ActiveNodes`, `CollapsiblePanel`, `DensityContext`, `ThinkingMonologue`.

No `fetch`/`/api/` usage found in `ChatInterface.tsx`, `CommandPalette.tsx`, `Sidebar.tsx`, `Inspector.tsx`, `ActiveNodes.tsx` in this pass (chat flows through parent `executeCommand` + Socket.IO).

## Tests

- `garage-ui/app/components/__tests__/EvalDashboard.test.tsx` (Vitest + RTL).

## Observations for downstream audits (not prescriptions)

1. **Port coupling**: Changing `KITTY_PORT` for Flask without a matching UI config leaves the UI pointing at `:5001` (see user-facing error string in `page.tsx` when SSE fails).  
2. **SourcePill URL model**: Relative `/api/source/...` may differ from absolute `:5001` calls depending on how Garage UI is served (standalone Next vs same-origin proxy). Worth tracing in deployment docs.  
3. **Single page**: All product UX is effectively one route; “polish gaps” in the audit spec likely refer to this surface and its modals/panels.

## Validation run for this document

```bash
cd garage-ui && npm run build
```

Result: success (see Build and framework).
