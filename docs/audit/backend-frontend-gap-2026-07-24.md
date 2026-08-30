# Kitty Backend Audit — 2026-07-24

**Scope:** All 47 gateway route files checked against front-end gateway.ts usage.
**Key finding:** 18 routes have zero or partial frontend wiring.

## Completely Unwired (12 routes)

These backend routes exist but the UI has no corresponding fetchers:

| Route File | What It Does | Priority |
|---|---|---|
| `calendar.py` | Calendar integration | Medium |
| `council.py` | Specialist council (agent-to-agent) | High |
| `desktop.py` | Desktop/computer control | Future |
| `extended.py` | Extended/advanced features | Medium |
| `feedback.py` | User feedback collection | High |
| `idea_mine.py` | Idea mining for insights | Medium |
| `import_chatgpt.py` | ChatGPT data import | Medium |
| `integrations.py` | External integrations | Medium |
| `kitty_tools.py` | Tool registry | Medium |
| `magic.py` | "Magic" features | Low |
| `telos.py` | Telos/research | Low |
| `voice.py` | Voice input/output | Medium |

## Partially Wired — Deep Tutor (4 routes)

| Route | Backend | Frontend |
|---|---|---|
| POST `/tutor/ask` | ✅ | ✅ `askTutor()` |
| GET `/tutor/quiz` | ✅ | ✅ `fetchTutorQuiz()` |
| POST `/tutor/attempt` | ✅ | ✅ `postTutorAttempt()` |
| POST `/tutor/learn` | ✅ | ❌ Cannot ingest docs from UI |
| GET `/tutor/review` | ✅ | ❌ Cannot see due reviews from UI |
| POST `/tutor/grade` | ✅ | ❌ Cannot grade answers from UI |
| GET `/tutor/term/{term}` | ✅ | ❌ Cannot see term mastery from UI |

The quiz loop works. Everything else — document ingestion, review, grading, mastery tracking — is backend-only. The UI cannot learn from documents.

## Expected Unwired (infrastructure)

| Route | Reason |
|---|---|
| `completions.py` | Called via `chat-client.ts` SSE stream, not gateway.ts |
| `onboarding.py` | Called directly by page.tsx fetch calls |
| `session_context.py` | Called via queries.ts hooks |
| `builder_control.py` | Builder is CLI-driven (not yet UI-driven) |
| `register.py` | Route registration only |
| `__init__.py` | Module init |

## Summary

- **47** backend route files
- **29** fully wired to frontend
- **12** completely unwired (backend exists, no frontend)
- **4** partially wired (Deep Tutor: ask/quiz/attempt only; learning/review/grading missing)
- **2** indirect/internal (completions, onboarding)
- **1** CLI-only (builder_control)

The single highest-impact gap: Deep Tutor can't actually *learn* from documents through the UI. The other 12 unwired routes represent features that exist in backend code but were never surfaced.
