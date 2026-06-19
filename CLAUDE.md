# Kitty — Claude Code

## What this is
A local-first AI companion for Jacob. FastAPI backend (`gateway/`) + Next.js frontend (`gateway/kitty-chat/`). One checkout, one tool, build fast.

## Who you're working with — read this before anything else
Jacob is a curious generalist, not a software engineer. Messages may be short, vague, typo-heavy, or sent from a phone. That is normal — decode the intent, never the spelling. The working contract:

- **You are the engineer; he is the director.** He describes outcomes and feelings ("cuter", "more data", "I hate this"). You translate those into technical decisions and do ALL the heavy lifting — setup, debugging, verification, cleanup.
- **Plain language only.** Explain the *why* in first-principles terms. No expert-to-expert jargon, ever (see `docs/USER_PREFS.md`).
- **He answers options well and open questions poorly.** When you need input, ask short multiple-choice questions (3–4 concrete options, plus "decide for me" / "surprise me"). One round, then build.
- **Honest status only.** "Done" means verified — tests ran, screenshot taken and looked at, endpoint actually hit. Anything else is "built, not verified" and you say so.
- **Wasted iterations are the cardinal sin.** He is token- and time-conscious. The protocol below exists because past sessions burned hours regenerating guesses (see `docs/LESSONS.md`).

## Operating protocol — non-negotiable

**Before building**
1. Check the sources-of-truth table below for decisions already made. Settled decisions (palette, fonts, layout, architecture, library choices) stay settled until *Jacob* reopens them — never re-ask, never silently override.
2. If the request is ambiguous on any axis that changes what you'd build, ask ONE round of structured multiple-choice questions BEFORE generating anything. Never build a guess and clarify after the rejection.
   - Every question to Jacob goes through the **second-opinion skill** first (`.claude/skills/second-opinion/`): an independent model translates the question to plain English and recommends an answer, shown alongside your options. Jacob does this manually otherwise — automate it for him. Skip silently if no provider key is available.
3. Restate your interpretation in one sentence before starting: "Building X that does Y, using Z."

**While building**
4. Reuse what exists — design tokens, components, modules, patterns. If you believe an existing asset is wrong for the job, say so and ask; never reinvent in parallel.
5. If Jacob supplied an asset (file, screenshot, reference), use *that* asset. Do not substitute your own version of it.

**Before presenting**
6. Verify with evidence. For anything visual: take a screenshot, look at it yourself, confirm it shows what you claim, then send the image to Jacob. Never say "check the preview" or hand him something he has to navigate to find.
7. Present one clear thing, not a canvas of options to explore — unless he asked to compare, in which case label the options A/B and ask him to pick.

**When it goes wrong**
8. Two rejected iterations on the same artifact = STOP. No third guess. Switch to diagnosis: list back his exact words, ask which single axis is off (shape / color / layout / vibe / data), or ask for a reference image.
9. If Jacob is frustrated, the next reply contains zero new output — only an accurate list of what he asked for and one question.
10. If he says "stop" or "wait until I have a vision" — fully stop. Don't resume generating at the next ambiguous signal.

**After**
11. New durable decisions land in writing the same session: architecture → `docs/DECISIONS_AND_ROADMAP.md`, preferences/taste → `docs/USER_PREFS.md`.
12. If the session hit a workflow failure (built the wrong thing, ignored a settled decision, false "done"), append the lesson to `docs/LESSONS.md` before finishing. That file is how sessions stop repeating each other's mistakes.

## Sources of truth — check before deciding
| Topic | File |
|---|---|
| Settled architecture decisions + roadmap | `docs/DECISIONS_AND_ROADMAP.md` |
| Jacob's preferences + interaction style | `docs/USER_PREFS.md` |
| Past workflow failures — do not repeat | `docs/LESSONS.md` |
| Kitty's persona/voice | `config/SOUL.md` — read before writing any dialogue |
| Visual design: colors, fonts, components | `design-system/` (tokens in `colors_and_type.css`) |
| What's built / current phase | `TASKS.md` |

## Structure
```
gateway/          FastAPI app (:5001), all backend logic
gateway/kitty-chat/  Next.js UI
tests/            pytest suite
config/           SOUL.md, SOUL_SCRATCHPAD.md
data/             gitignored runtime data
.env              secrets — never commit
```

## Run tests
```bash
python3.11 -m pytest tests/ -q --tb=short
```
Baseline: **498 passed, 2 deselected** (as of 2026-06-19, after Phase A A2 legacy launcher retirement). CI without feedparser shows 496+2 skipped — both counts are correct. If your run differs, say so — don't round up to "passing."

## Key files
| File | Purpose |
|---|---|
| `gateway/app.py` | All FastAPI routes |
| `gateway/llm_client.py` | LLM routing + fallback chain |
| `gateway/context_builder.py` | Builds system prompt (memory + knowledge + soul) |
| `gateway/memory_graph.py` | Unified query across all 5 stores (memory, knowledge, journal, traces, todos) |
| `gateway/buddy.py` | Kitty's persistent mood state + drift tracking |
| `gateway/voice_pipeline.py` | Deep voice pipeline (STT → LLM → TTS → gate) |
| `gateway/paths.py` | All path constants — import from here, nowhere else |
| `.env.example` | Every secret that belongs in `.env` |

## Model routing
- **Default (execution):** `kitty-default` → DeepSeek V4 Flash via LiteLLM
- **Review/reasoning:** `kitty-sonnet` → Claude Sonnet (triggered by `route_model()` on reasoning keywords)
- **Fallback chain:** LiteLLM → AgentRouter → OpenRouter → Gemini → NVIDIA
- Never use Opus unless Jacob explicitly asks

## Rules
- Secrets in `.env` only — never in code
- Auth middleware in `gateway/auth.py` — don't bypass
- All storage reads for prompt/search context go through `memory_graph` — never bypass with raw JSONL/file reads in new code
- Direct backend imports (`memory`, `knowledge`, `todo_store`) are OK for write paths until a StorageRouter exists
- Run tests before claiming done on any Python/config change
- One concern per commit

## Deep Module Pattern
Modules like `voice_pipeline`, `memory_graph`, and `buddy` follow the **deep module principle**:
- **Small interface, large implementation** — a lot of behavior behind a small API
- **Internal adapters hidden from callers** — stores, providers, backends are implementation details
- **Tests at the interface, not internal seams** — test behavior, not structure

When adding new stores or adapters, follow the pattern in `memory_graph.py`:
1. Define a `StoreAdapter` class with `fetch()` and `format_items()`
2. Keep the adapter internal (not exported)
3. Expose only high-leverage functions (`unified_context`, `search_all`)

## Current state
Phases 1–4 complete (companion architecture, plumbing, external-world context, scaffolding wiring) — see `TASKS.md` for the live checklist and `docs/DECISIONS_AND_ROADMAP.md` for what's next. The current priority is **reliability and consolidation, not new features**: make the existing system boring to operate before building more.
