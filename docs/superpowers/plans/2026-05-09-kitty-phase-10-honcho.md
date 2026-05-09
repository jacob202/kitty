# Phase 10 — Honcho Weekly Mirror & Seeding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate the Honcho psychology layer to track Jacob's behavioral patterns and provide a "Weekly Mirror" — a gentle, insightful observation of his progress and loops.

**Architecture:**
1. `gateway/honcho.py` (already partially built) interfaces with the Honcho API.
2. Ingest past conversations to "seed" the Honcho profile.
3. n8n triggers a weekly aggregation of signals.
4. Kitty presents the observation to Jacob.

**Tech Stack:** Python 3.12, Honcho API, Mem0 (for pattern storage).

---

## Task 1: Historical Seeding

- [ ] **Step 1: Process old chat logs through Honcho**
- Use a local model (Hermes 3B) to extract signals from `data/imports/` if cost is an issue, or DeepSeek Flash for speed.

---

## Task 2: Real-time Signal Extraction

- [ ] **Step 2: Update Gateway to send every conversation turn to Honcho**
- Asynchronous call to `add_honcho_signal`.

---

## Task 3: Weekly Mirror Generation

- [ ] **Step 3: Implement weekly summary logic**
- Look at the last 7 days of signals.
- Identify the strongest theme (e.g., "consistent recovery wins" or "over-planning loop").
- Draft a 3-sentence observation in Kitty's "warm tabby" voice.

---

## Verification

Gate: Run the weekly mirror script manually. It should produce a non-generic observation based on real data from the last week.
