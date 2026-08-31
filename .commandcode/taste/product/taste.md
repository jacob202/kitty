# Product

- Every UI surface must be actionable: no information without a corresponding action right there — e.g., in the work tab the user should be able to perform work, fix packets/blocks, deploy, create, plan; this applies to the entire UI. Confidence: 0.95
- User-facing copy must be free of packet IDs, ports, env vars, raw HTTP status, stack traces, internal service names, terminal commands, and Mac paths. Confidence: 0.95
- Keep personality in the UI but remove decorative cards that don't support a decision or action. Confidence: 0.8
- Home should answer what matters now, what the system is doing, and what the user can do next. Confidence: 0.7
- Acceptance must cover desktop and iPhone-class (mobile) widths with no horizontal overflow, clipped dialogs, dead primary controls, or contradictory status. Confidence: 0.9
- Verify degraded/unavailable states explicitly (e.g., gateway stopped, renderer unavailable) — surfaces must stay usable and say plainly that generation is disabled rather than hiding it. Confidence: 0.85
- Distinguish similar states clearly in the UI (e.g., saved vs indexed vs indexing-failed vs content-unavailable). Confidence: 0.6
- Prefer small change packets with exact allowed paths and no scope creep; one owner and explicit acceptance checks per slice. Confidence: 0.75
- Don't create parallel subsystems (model registry, queue, artifact store, frontend state machine) just to make the UI easier — reuse existing systems. Confidence: 0.6
- Prefers a warm, hand-drawn, character-first visual identity — a mascot with real expressive states as the product's personality anchor (he cites Anthropic's hand-drawn mascot warmth as the reference) — and dislikes the generic SaaS look: blue-violet "AI-startup default" accents, terminal-mono "developer tool" styling, and hover-only affordances. Confidence: 0.85
- Prioritizes fixing design basics (real workflows and what's wrong with how someone actually uses the product) before finishing details (graphics, font, color); "a better Kitty, not a prettier one" — functional improvements are sequenced ahead of polish. Confidence: 0.8
