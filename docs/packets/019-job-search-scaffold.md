# Packet 019 — Job search scaffold

- **Status:** ⏸ parked by Jacob's explicit call (2026-07-04): *"plan it,
  don't build it."* The near-term income track is disability (SAID/CDB/DTC,
  packet 017), not employment. This file exists so the plan is honest about
  the whole map; it activates only when Jacob says "activate job search."
- **Best executor:** Claude Code / Codex when activated.
- **Purpose:** When the right time comes, Kitty runs the search instead of
  Jacob staring at boards: watched searches surface matches, applications
  get drafted as T1 artifacts, and the first B (per packet 016) is
  rebuilding the résumé — he hasn't worked in ten years and doesn't have
  one, so the scaffold starts there, not at cover letters.

## Scope sketch (deliberately thin until activation)

- Register `job-search` as a non-code project (006 table).
- Résumé rebuild as the project's standing first next-action: an
  interview-style capture flow (Kitty asks, Jacob talks, T1 draft comes
  back) — the journal/interview machinery is the seed.
- Watched searches via `web_monitor.py` → signals → weekly digest section,
  passive mode ("just watching for the right thing") by default.
- Match write-ups and application drafts as T1 artifacts in the action
  queue. Nothing is ever submitted by Kitty (submission is T3 until the
  tier sheet says otherwise).

## Dependencies

- 015 (delivery), 016 (the B), web_monitor signal wiring (shipped, #77).

## Activation criteria

Jacob says so. Nothing else — no date, no metric, no nudging. If packet
016 ever generates "activate the job search" as a B, that is a bug; the
navigator does not get to make this call.

## Jacob reviews

- Everything, on activation. This packet gets a full authoring pass then.
