# Skill Audit — Kitty Repo, July 2026

## Active Skills (10)

### Utility (reusable, does one thing well)
| Skill | Location | Notes |
|-------|----------|-------|
| **debug-fix** | `.claude/skills/` | Bug finding/fixing. Default careful, `--fast` for hotfix mode. |
| **catchup** | `.claude/skills/` | Session context rebuild after /clear. Reads STATE.md + handoff. |
| **image-gen** | `.agents/skills/` | ComfyUI-backed image generation. Kitty-specific. |
| **provider-credit-debugging** | `.agents/skills/` | Debug API keys, credits, token usage across OpenRouter/DeepSeek/LiteLLM. |
| **journal-entry** | `.agents/skills/` | Guided journal interview + synthesized entry save. |

### Verification (checks quality of output)
| Skill | Location | Notes |
|-------|----------|-------|
| **second-opinion** | `.claude/skills/` | Automatic — runs before asking Jacob a decision. Pipes question through second LLM. |
| **isa** | `.agents/skills/` | Ideal State Artifact — scaffolds specification docs, checks completeness, reconciles. Heavy orchestration but primary function is verification against ideal state. |

### Orchestration (chains other skills)
| Skill | Location | Notes |
|-------|----------|-------|
| **remember** | `.claude/skills/` | Captures durable preferences to PREFERENCES.md. Persists across sessions. |
| **mcp-kitty-council** | `.agents/skills/` | Kitty Council MCP server — multi-stage agent routing. |
| **improve-codebase-architecture** | `.agents/skills/engineering/` | Finds deepening/refactoring opportunities. Kitty domain-language aware. |

## Archived Skills (8) — in `_archive/`

All are high-effort reasoning frameworks. Currently unused. Keep archived unless daily use returns.

| Skill | Bucket | Why archived |
|-------|--------|-------------|
| extract-wisdom | Data Enrichment | Content extraction. Replaced by fabric CLI + simpler approaches. |
| first-principles | Orchestration | Physics-based reasoning. Heavy ceremony for most tasks. |
| iterative-depth | Orchestration | Multi-lens analysis. 30-50% more criteria; high token cost. |
| iterative-self-review-meta-optimization | Verification | Multi-pass critique. Replaced by simpler review patterns. |
| red-team | Verification | 32-agent adversarial analysis. Useful for strategy, not code. |
| root-cause-analysis | Orchestration | Incident investigation (5 Whys, fishbone, postmortem). |
| science-method | Orchestration | Hypothesis-driven experimentation. Scales across micro→macro. |
| systems-thinking | Orchestration | Causal loops, archetypes, leverage points. |

## Gaps (nothing in Kitty covers these)

- **Chat-history ingestion from external tools (Codex, ChatGPT, OpenCode):** Nothing exists. The `add-new-resource` skill in `~/kb` fills this gap.
- **Self-improving system loop:** Nothing exists. The `improve-system` skill in `~/kb` fills this gap.
- **Cross-tool session state:** No single source of truth for what shipped across tools. `~/kb/SHIPLOG.md` + the hooks pattern fills this.

## Duplicates / Combine Candidates

- `science-method` and `first-principles` overlap on hypothesis generation. Both archived — no action.
- `iterative-depth` and `systems-thinking` both ask "what am I missing?" from different lenses. Both archived.
- `iterative-self-review-meta-optimization` and `second-opinion` overlap on review. `second-opinion` is the active, lightweight version.

## Recommendation

None to delete (archives are already quarantined). No active overlap. Two gaps filled by the `~/kb` skills built in Steps 4 and 6.
