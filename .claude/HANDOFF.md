# Session Handoff — 2026-07-05 (Fable overnight/day session)

## What happened (in order)

1. **Shipped the packet run:** 015 phone channel (#103), 021 project
   registry (#106), 016 next-step navigator (#107) — each built, tested,
   manually verified against a real gateway, PR'd, merged.
2. **Jacob went live.** First time Kitty actually ran for him:
   - Fixed his stale local main (two macOS `Icon\r` files inside `.git/`
     broke pulls — `find .git -type f -iname 'Icon*' -delete`).
   - LiteLLM wouldn't start: `~/kitty-services/venv-litellm` was missing
     the proxy extras → `pip install 'litellm[proxy]'` fixed it (plus its
     cold start is now slow — doctor can race it; re-run doctor).
   - Another `Icon\r` inside the project venv broke chromadb — same fix.
   - Gmail OAuth completed (Desktop-app client), `PUSH_IMESSAGE_RECIPIENT`
     set. **Doctor: pass=11 warn=1 fail=0.** First real B generated.
3. **Wave-3 hardening from watching him live** — PR #109: refresh degrades
   instead of 500ing when the model is down (D9 shape), PATCH /projects,
   `./kitty project add|list|refresh|next|set-path`, doctor `env:parse`
   (his `.env` line 1 has a stray quote — still there, cosmetic), source
   timeout 5→10s.
4. **Docs close-out + wave 4 open** — this PR: 016 flipped to shipped;
   021/022 numbering collision from #101/#102 fixed (files renumbered
   023/024, registered, L-CAND-12 written, intake gate now names the
   rule); **017 authored executor-ready** (Wave 4 = move-in day);
   **025 authored** (imagegen v2 — Jacob's explicit request).

## Live warnings for the next session

- **Jacob pasted his entire `.env` (all API keys) into chat twice.**
  Advised rotating GITHUB_PAT + legacy token at minimum. Not done as of
  handoff — worth a gentle check-in, not a lecture.
- His live imagen checkout is under `~/Projects/`, NOT this repo's
  `mcp/imagen/` copy ("it's in projects not kitty") — 025 step 0 covers
  the reconciliation. Do not build imagen features into this repo's copy
  without doing that preflight.
- `python-dotenv could not parse statement starting at line 1` on every
  command on his Mac = the stray quote, not a real failure. #109's doctor
  check names it; the fix is deleting one character in `.env` line 1.
- Codex's 008-remainder worktree claim is from 2026-07-04 and hasn't been
  heard from — verify before treating it as taken.

## The thread (D13 context, do not lose)

Jacob's sequencing, his words: build the basic thing, verify it works,
THEN "magic kitty" — cross-project insight (packet 022). 016's week of
real Bs is the verification step. Magic comes next, not never, and not
smuggled into 016.

## Open PRs at handoff

- #109 wave-3 hardening (CI was running; merge when green)
- wave-4 docs PR (this branch)
- #108 registry flip — superseded by the docs PR; close it
