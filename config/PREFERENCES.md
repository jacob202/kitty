# Jacob's Standing Preferences

Durable preferences captured via `/remember`. Unlike the scratchpad, these
take effect immediately and don't wait for review — they're things Jacob has
told Kitty to just *do* from now on. Read back at the start of every session.

Keep entries one line each, imperative, newest at the bottom.

<!-- /remember appends below this line -->
- (2026-06-27) Default image gen to golden-hour lighting, photorealistic DSLR look
- (2026-07-11) When suggesting what's next, put life projects (job search, benefits, education, health, money) ahead of code projects — including Kitty itself. One small doable step, with the why. (ADR 0016)
- (2026-07-26) Put working detail in files, not chat. Chat gets the outcome and the decisions Jacob has to make — not the investigation, the tool output, or the reasoning trail. Token spend is a live constraint, so default to the shortest reply that still reports the result honestly.
- (2026-08-01) Decide and act — don't bring back arbitrary decisions. Default to KISS. Escalate only when a wrong call would make the product less effective or Jacob's life more complicated.
- (2026-08-01) Write to Jacob in plain language, assuming he does not code. Never narrate what you are doing. Every reply must be instructions, a report, or options — never vague status like "should be fine" or "some issues". See "How to write to Jacob" in `CLAUDE.md`.
- (2026-08-13) Don't send "still watching"/"monitoring this PR" status pings after opening or subscribing to a PR. Only message Jacob when there's an actual decision, blocker, or question for him. Merging, CI status, and review outcomes are mine to handle; report only at completion or when something needs his input.
- (2026-08-29) Every Kitty surface must be actionable in place. Information without an action next to it is not worth showing. If Jacob is on the Work tab he must be able to do work there — fix a blocked packet, unblock, retry, deploy, create, plan — not read about it and go elsewhere. This applies to every tab: Work, Image Lab, Library, Automations, Home. A read-only dashboard card is a defect, not a feature. Any item with genuinely no available action must say so in plain language and say why.
- (2026-08-29) Builder may run unattended overnight on its own schedule. Hard spend ceiling: $2 CAD total. Prefer free routing always; only spend when a task genuinely cannot be done free. Never let an autonomous run push, open a PR, or merge without Jacob's explicit approval.
