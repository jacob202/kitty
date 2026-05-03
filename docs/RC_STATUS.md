# RC Status — 2026-04-29

**Tag:** `rc-scope-locked-20260429`

## Scope

| Area | Status | Notes |
|------|--------|-------|
| Tests | 348 passed, 2 warnings | Golden gate |
| Auth | OpenRouter-only | Anthropic fallback removed |
| API routes | /brief, /command, /chat, /eval | All verified HTTP 200 |
| Golden demo | scripts/golden_demo.sh | 3-minute end-to-end |
| Session start | scripts/start-session.sh | One-command setup |

## In scope (frozen)

- `/api/brief` — deterministic control-doc brief
- `/api/command` with `/stuck` — next action
- `/api/chat` — OpenRouter fallback
- `api/eval/dashboard` — eval artifact summary
- Domain news feed — wired into specialist context
- Canadian-first assistant persona (permanent)
- `.claude/skills/` — audit, demo, spec, fix-and-verify, overnight-queue, parallel-subagents, prompt-answer-quality, spec-to-impl (project skills; `domain-news` / `recommend` removed 2026-05)

## Out of scope (parked until RC signoff)

- Browser smoke flows
- Artifact capture + daily summary
- Self-improving eval loop
- Swarm productization
- Bank transaction analysis
- Physical `kitty-system` split
- `$129/month` pricing (treated as noisy extraction)

## Open loops

- Physical `kitty-system` split decision

## Release gates

```bash
bash scripts/start-session.sh     # All-in-one health check
bash scripts/golden_demo.sh       # 3-minute e2e smoke
/opt/homebrew/bin/python3.12 -m pytest tests/ -q  # Tests only
git status                         # Clean tree
```
