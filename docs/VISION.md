---
type: vision
title: "Kitty Vision"
status: canonical
owner: jacob
primary_purpose: Why Kitty exists, what organization we are building, and the permanent missions that guide every decision
derives_from: []
implements: []
referenced_by:
  - docs/CONSTITUTION.md
  - docs/ROADMAP.md
  - docs/engineering/ARCHITECTURE.md
review_cycle: annual
---

# Why Kitty Exists

Kitty is not a coding project. Kitty is how Jacob gets help that money usually gates: structure, memory, follow-through, and a patient second brain that shows up every single day.

The expensive reasoning models were only ever used to design the system. The design is done and written down. What remains is bounded implementation, and the whole KittyBuilder pipeline was built precisely so cheap and free models can do that safely.

## What Organization We Are Building

A personal operating layer — a control plane for one person's life. Not an AI assistant. Not an autonomous agent swarm. A trusted front door that maintains the live state of Jacob's life and projects, tells him what changed and what matters, and converts that into prepared, approvable actions.

The companion persona is the interface contract — the voice and taste through which the operating layer speaks — not the product itself.

## Permanent Missions

### 1. The Resume Loop

Open Kitty at any time and within five seconds know: what happened while you were away, what's next, and what needs you. Continue any of it in one tap.

Every feature is judged by: does it make resuming easier, or is it a dashboard tile?

### 2. Life-First Ordering

When Kitty generates "What's Next", life projects (job search, benefits, education, health, money) outrank code projects — including Kitty itself. Kitty must never become a hobby that eats the time it was built to free.

### 3. Honesty Over Performance

Nothing fake. No hardcoded data panels. No silent fallbacks presenting broken integrations as working. Failures surface as failures. Empty states are explicit. The trust contract is: Kitty never pretends something works when it doesn't.

### 4. Local-First Privacy

State, memory, preferences, and the control layer live on the Mac. Cloud models are rented reasoning, never the system of record. What Kitty knows about Jacob belongs to Jacob.

### 5. Bounded Execution

Every action Kitty takes is a recorded row with a preview of exactly what will happen and a result of exactly what did. Approval tiers are enforced in code, not by prompt discipline. The queue is the audit log of everything Kitty ever did on Jacob's behalf.

### 6. Compound Organizational Judgment

Every session should leave the repository better than it found it. Decisions are recorded. Lessons are promoted. Documentation behaves like an engineered system. The organization's knowledge compounds over time instead of evaporating between sessions.

## What "Done" Looks Like

Not a finished app. A morning ritual that holds:

- Jacob opens Kitty. It says what happened, what's next, what needs him — truthfully, in his own projects' terms.
- The next move is small enough to actually do, and doing it compounds.
- When something breaks, Kitty says so plainly and it's fixable by a free worker with a bounded packet.
- Nobody involved has to pretend something works when it doesn't.

That's the whole dream, and every piece of it already has rails in this repo.

## What Kitty Is Not

- A therapy, coping, or recovery app.
- A mascot toy. The cat is a state gauge; the state machine behind the face is the product.
- A generic chatbot with plugins.
- A dashboard for its own sake. Panels that display without enabling action are cut.
- A ten-year privacy startup. The near-term work matters; the grand vision explains what it's for.
