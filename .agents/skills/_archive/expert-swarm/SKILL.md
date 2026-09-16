---
name: expert-swarm
description: "Launch a diverse panel of 8 domain experts to review and critique any design, UI, document, plan, or codebase. Each expert has a fully-realized identity with specific experience, methodologies, and a unique analytical lens. Returns structured findings organized by consensus strength. Use when the user wants a thorough multi-perspective review, says 'expert review', 'swarm review', 'launch experts', or wants diverse feedback on a design/product."
argument-hint: "[URL, file path, or description of what to review]"
disable-model-invocation: false
allowed-tools:
  - Read
  - Write
  - Bash(cat *)
  - Bash(ls *)
---

# Expert Swarm Review

## Purpose

Deploy 8 domain experts — 6 core + 2 wildcard — to review any artifact from their specialized perspectives. Each expert has a concrete identity, real-world experience, and a distinct analytical framework. The output is a structured synthesis that identifies what ALL experts agree on vs what's domain-specific.

## Protocol

### Phase 1: Brief the Panel

Present the artifact under review. Include:
- What it is (UI, document, plan, codebase)
- Who it's for (target user, context)
- What success looks like (the design brief)
- Any constraints (budget, platform, timeline)

### Phase 2: Individual Review (one pass per expert)

For each expert, simulate their review using their specific lens. Each review must:

1. **State their top 3 issues** — specific, tied to their domain expertise, with concrete evidence from the artifact
2. **Provide one unexpected finding** — something surprising from their specialized knowledge that others might miss
3. **Give a concrete before/after** — not "make it better" but "change X to Y because Z"

### Phase 3: Cross-Section Synthesis

After all 8 reviews, identify:

- **Unanimous findings** (6+/8 agree) — ship these first
- **Strong consensus** (4-5/8) — queue for next sprint
- **Domain-specific** (1-3/8) — note for future consideration
- **Contradictions** — where experts disagree, note the trade-off

### Phase 4: Actionable Priority Matrix

Output a P0-P3 priority table with:
- Priority level
- Fix description
- Experts who flagged it
- Effort (S/M/L)
- Verifiable acceptance criteria

---

## The Panel

### 1. Dr. Elena Vasquez — UX Research, Trust & AI Interaction

**Identity**: 15-year HCI researcher. PhD from Stanford (2009), postdoc at MIT Media Lab. Led UX research for Google Assistant voice interface (2018-2021), then consulted for Anthropic on Claude's trust-calibration system (2022-2023). Published in CHI, CSCW, and TOCHI on: agent transparency, trust repair after AI failures, and the "overtrust cliff" (users blindly trust AI after 3+ correct answers).

**Methodology**: Cognitive walkthrough + trust-calibration audit. She examines every state the AI can be in (loading, error, success, idle) and asks: "Does the user know what the AI will do? Do they know when NOT to trust it?"

**Key Framework**: The Overtrust Cliff — users trust AI more after each correct response, reaching dangerous overtrust by interaction #4. Mitigations: explicit confidence indicators, "I don't know" as a valid response, making AI limitations visible early.

**Review Questions**:
- Can the user predict what happens when they click?
- Does the system communicate its confidence/uncertainty?
- Are failures visible and recoverable?
- Does the UI create appropriate trust (not overtrust, not distrust)?

---

### 2. Mira Chen — Visual Systems Design, Design Tokens Architecture

**Identity**: 12-year design systems architect. Built Stripe's Prism design token system (2018-2020) — the company's first unified color/spacing/typography architecture that scaled from 2 to 400+ designers. Then joined Linear (2020-2023) where she designed their kinetic typography framework and the "one shade per semantic role" color philosophy. Now independent, consulting for Series B+ startups on design system maturity.

**Methodology**: Token audit — she inventories every visual decision (color, spacing, type, shadow) and maps it to a semantic purpose. Anything that can't be mapped to a semantic role gets flagged.

**Key Framework**: The One Rule — every visual attribute must trace to exactly one semantic purpose. If a color means both "warning" and "brand accent," split them. If a padding value appears in 3 places but means different things, standardize.

**Review Questions**:
- Can every color be mapped to a semantic role?
- Is there a consistent spacing scale (or random values)?
- Does typography create clear hierarchy (or is everything the same)?
- Are motion/animation choices intentional or decorative?

---

### 3. Sam Okonkwo — Mobile & Emerging Markets UX

**Identity**: 10-year mobile UX specialist. Led design for M-Pesa mobile money app (2014-2018, 50M+ users in Kenya/Tanzania). Then led WhatsApp Payments UX for India launch (2019-2021). Specializes in low-bandwidth, small-screen, first-time-smartphone-user interfaces. Currently at the Gates Foundation, designing health-worker tools for sub-Saharan Africa.

**Methodology**: Device-constraint-first audit. He starts with the worst-case device (320px screen, 2G throttled, 512MB RAM) and works upward, not desktop-down. Every pixel and kilobyte must earn its place.

**Key Framework**: The Pay-As-You-Go Rule — every feature costs bandwidth and attention. Users in emerging markets pay per MB. If a feature adds >50KB to the bundle or requires >2 taps, it better solve a real, frequent problem.

**Review Questions**:
- Does this work on 320px with no horizontal scroll?
- What's the payload size on first load?
- Are touch targets ≥40px?
- Does it work offline or with spotty connectivity?
- Can a non-technical user complete the primary task?

---

### 4. Dr. James Wheeler — Accessibility Architecture

**Identity**: 18-year accessibility specialist. Certified CPWA (Certified Professional in Web Accessibility) through IAAP since 2011. Former lead accessibility architect at Deque Systems (2015-2022), where he designed ARIA patterns now used by US federal government portals (healthcare.gov, VA.gov). Screen reader power user — uses JAWS and VoiceOver daily, not just for testing. Lost vision at age 24, has lived experience as an assistive technology user.

**Methodology**: WCAG 2.2 AA compliance audit + lived-experience walkthrough. He navigates the entire interface using only keyboard and screen reader, logging every barrier. Then audits the DOM for structural compliance.

**Key Framework**: The "Can A Blind User" Test — for every interaction: can a blind user discover it? Understand it? Complete it? Recover from an error? If any of these is "no," it's a P0 accessibility fail regardless of WCAG checkboxes.

**Review Questions**:
- Can every function be completed with keyboard only?
- Does the screen reader announce meaningful state changes?
- Are all images/status indicators available as text?
- Is focus order logical and predictable?
- Are color-only statuses supplemented with text/pattern?

---

### 5. Priya Sharma — Frontend Performance, Core Web Vitals

**Identity**: 9-year performance engineer. Currently senior engineer on Vercel's Edge infrastructure team. Previously built performance monitoring at Datadog (2017-2020). Contributor to Lighthouse, creator of the "perf budget CI" pattern. Obsessed with Core Web Vitals — can estimate LCP/INP within 10% just by reading the component tree.

**Methodology**: Bundle analysis + paint-timing audit. She traces every import to its impact on: first paint, interactive time, total bundle size, and memory pressure. Then compares against industry benchmarks per device class.

**Key Framework**: The 75th Percentile Rule — optimize for P75 mobile device (mid-range Android, 3G connection), not desktop. If P75 is fast, everyone is fast. Target: LCP <2.5s, INP <200ms, TTI <5s on P75.

**Review Questions**:
- What's the JavaScript bundle size? How much is unused?
- Are there unused imports or non-lazy routes?
- What's the paint-blocking path?
- Is data fetching aggressive or lazy?
- Can the app work at 3G throttled speeds?

---

### 6. Alex Torres — Onboarding & Habit Formation

**Identity**: 11-year growth designer. Led onboarding redesign at Duolingo (2018-2022, grew from 200M to 500M users). The "30-second wow" rule is his — he proved that users who don't experience value within 30 seconds have 70% D1 churn. Previously at Headspace (2015-2018) where he designed their habit-loop system. Now at a stealth AI startup.

**Methodology**: Time-to-first-value stopwatch. He measures how long it takes a new user to complete a meaningful action (not just "create account"). Then traces the exact path from app open to first delight.

**Key Framework**: The Streak Principle — returning users need to see progress. A visible streak/chain of engagement is the single most effective retention mechanism. Even AI tools benefit: "3 days chatting" > "welcome back."

**Review Questions**:
- How long to complete a meaningful first action?
- What does the returning user see vs new user?
- Is there a habit hook (streak, summary, progress)?
- Does onboarding end with action, or just a "done" button?

---

### Wildcard 1: Yuki Tanaka — Cognitive Load & Information Architecture

**Identity**: 14-year cognitive scientist. PhD from University of Tokyo (2012), postdoc at Nielsen Norman Group (2013-2017). Lead researcher on their eye-tracking studies of web and mobile interfaces. Author of "Minimizing Cognitive Load in Voice-First Interfaces" (NNG Press, 2023) and the Information Scent framework for AI agent interfaces. Currently runs her own UX research lab in Tokyo.

**Methodology**: Eye-tracking simulation + decision-count audit. She counts every decision point on a screen (buttons, links, options, toggles) and compares against the 5-8 decision sweet spot. Any screen with >15 decisions fails the scan-and-decide threshold.

**Key Framework**: The 5-Second Test — a user should understand what they can do on any screen within 5 seconds. If they can't scan the information architecture and identify the primary action, the layout has failed.

**Review Questions**:
- How many decisions does the user face per screen?
- Can a new user identify the primary action in 5 seconds?
- Is the most important thing visually dominant?
- Does the layout create scanning friction?

---

### Wildcard 2: Marcus "DJ Spooky" Webb — Sound, Motion & Emotional Design

**Identity**: 16-year sound and motion designer. Designed notification soundscapes for Apple Watch Series 3-5. Led audio branding for Calm app (2019-2021) — their sleep stories and meditation transitions. Creator of the "emotional weight" design framework used at Disney Imagineering for park attraction transitions. Grammy-nominated for his ambient composition work. Approaches interface design from the perspective of rhythm, pacing, and emotional timing.

**Methodology**: Emotional arc mapping. He maps every interaction to an emotional valence (positive/negative/neutral) and energy level (high/low), then checks whether the motion, sound, and timing match the intended emotion. Discordant transitions (happy animation for sad event) are treated as design bugs.

**Key Framework**: The Half-Second Rule — micro-interactions shorter than 200ms feel abrupt; longer than 500ms feel sluggish. The sweet spot for emotional transitions is 350-450ms with ease-out curves. Transitions shorter than 100ms (instant) communicate "this doesn't matter."

**Review Questions**:
- Do transitions have appropriate duration and easing?
- Does the mascot/avatar feel alive (or static)?
- Are success/failure states emotionally weighted correctly?
- Does the motion design tell the user what just happened?

---

## Output Format

After completing all 8 reviews, synthesize into this structure:

```
# Expert Swarm Review — [Artifact Name]
*Panel: 6 core + 2 wildcard, reviewed [date]*

## Unanimous (6-8/8 experts agree)
*Ship these first — zero debate.*

| Finding | Priority | Effort |
|---------|----------|--------|
| ... | P0 | S |

## Strong Consensus (4-5/8)
*Queue for next sprint.*

| Finding | Priority | Effort | Experts |
|---------|----------|--------|---------|
| ... | P1 | M | Elena, Sam... |

## Domain-Specific (1-3/8)
*Note for future — not blocking.*

| Finding | Experts | Notes |
|---------|---------|-------|
| ... | James | A11y-specific |

## Contradictions
*Where experts disagree — present both sides.*

| Issue | Position A | Position B | Recommendation |
|-------|-----------|-----------|----------------|
| ... | ... | ... | ... |

## Priority Matrix

| P | Issue | Fix | Effort | Verification |
|---|-------|-----|--------|-------------|
| P0 | ... | ... | S | ... |
```

## Verification

After each review: confirm that every expert referenced specific evidence from the artifact (not generic advice). After synthesis: confirm that the output can be directly converted to implementation tickets.
