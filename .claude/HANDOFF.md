# Handoff — 2026-07-25 — gateway-packages (research reframed, doc not written)

<!-- kitty-handoff
{
  "schema_version": 1,
  "updated_at": "2026-07-25T12:00:00Z",
  "head_sha": "ac898f9",
  "branch": "gateway-packages",
  "worktree": ".",
  "status": "valid",
  "completed_items": [
    "Codebase sync: ./kitty context --agent ran, continuity check passed",
    "Phase 0 competitive analysis appended to docs/PLANS.md line 153 — 7 initiatives, 27 packets (UX, MOB, ARCH, A11Y, I18N, FEAT, DEVOPS)",
    "Raw research data fetched for 6 repos: Open WebUI (146k), Goose (51k), LibreChat (41k), Khoj (36k), Chatbot UI (33k), AionUi (31k)",
    "Source pulled: OnBoarding.svelte, ChangelogModal.svelte, NotificationToast.svelte, SlideShow.svelte, shortcuts.ts, app.css, docker-run.sh (Open WebUI); download_cli.sh + AGENTS.md (Goose); directory trees for all 6",
    "Top-voted issues mined from Open WebUI and LibreChat (list below)",
    "Wrote docs/research/MATURE_AI_PRODUCT_RESEARCH.md — 7 themes, organized by theme not repo, every claim linked to a fetched primary source or labelled as inference",
    "Verified prior session's issue data against the GitHub API — titles, comment counts, and reaction totals all matched"
  ],
  "blockers": [],
  "next_action": "docs/research/MATURE_AI_PRODUCT_RESEARCH.md is written — 7 themes, primary sources verified. Gaps named in its final section: mobile UX, agent visibility, community sources (Reddit/HN/dev.to), commit archaeology. Next pass starts there. Do NOT edit docs/PLANS.md.",
  "invalidation_conditions": [
    "HEAD changes beyond ac898f9",
    "branch changes off gateway-packages"
  ],
  "active_mission": "docs/ACTIVE_MISSION.md",
  "pull_request": null
}
-->

## State

Branch `gateway-packages` at `ac898f9`. **Working tree is not clean** — `.claude/HANDOFF.md`
and `docs/PLANS.md` are both modified and uncommitted. HEAD is six commits past the
`b78215ef` the previous handoff referenced; those six are an unrelated package-restructure
campaign (builder, memory, image, voice, stores moved into subpackages). That refactor is a
separate workstream from the research below — check with Jacob before assuming either is
finished.

## The reframe

Jacob stopped the feature-comparison approach mid-session and redirected. The comparison
table was judged too superficial. New requirements:

- Organize by **recurring themes across projects**, not by repository
- Sources must include commit history, major rewrites, controversial PRs, long issue
  threads, maintainer discussions, Reddit, HN, dev.to, engineering blogs, release notes,
  architecture docs
- Explain **why** decisions were made, not what was decided
- Should read like an internal design handbook, not a bake-off
- Existing PLANS.md work is preserved as Phase 0 hypotheses — leave it alone
- New document: `docs/research/MATURE_AI_PRODUCT_RESEARCH.md` (directory exists, empty)

## Data collected but unused

Open WebUI issues (reactions / comments):
- #23990 scrolling jumps in conversations (39/27)
- #21564 edit-and-continue response bugs (38/42)
- #20629 MCP server response fails (23/23)
- #24553 API chat completions NoneType error (19/51)
- #16303 GPT response parsing (18/65)
- #25585 web search results not passed to model (16/54)
- #21348 reasoning trace splits browser to halt (12/50)

LibreChat issues:
- #4848 chat folders/projects (176/58)
- #3137 admin user management (113/56)
- #11106 agent skills support (72/27)
- #1215 show conversation cost (69/36)

Code artifacts: Goose `download_cli.sh` (~1500 lines of OS detection, error handling, PATH
management); Open WebUI onboarding = SlideShow + OnBoarding + ChangelogModal composition.

## Themes to cover

1. Installation & onboarding — most data already in hand
2. Streaming & latency masking — needs data
3. Navigation & mobile UX — partial, from Open WebUI component structure
4. Configuration & settings — LibreChat yaml collected
5. Agent visibility & task management — needs data
6. Error recovery & trust — issue data collected
7. Extension ecosystems & discoverability — needs data

Plus community research (Reddit, HN, dev.to, engineering blogs) across all themes — none
collected yet.

## Note on the previous draft

The draft handoff referenced a `todos` tool "initialized with 10 items". No such state
persists across sessions — the theme list above is the only carry-over. Don't go looking
for it.
