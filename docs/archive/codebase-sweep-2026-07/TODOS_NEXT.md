# Next Steps Implementation Plan

## Overview
Implementing all 5 next steps from `docs/retired/ARCHITECTURE_COMPLETE.md`

## Phase A: Cron Schedule Editor UI ✅
- [x] Create CronScheduleEditor component
- [x] Wire to /cron/* endpoints
- [x] Show schedules list with toggle/delete
- [x] Add "Create Schedule" form
- [x] Display last run, next run, status

## Phase B: Performance Instrumentation ✅
- [x] Add token usage logging to llm_client.py
- [x] Add latency tracking to memory_graph.py
- [x] Create /perf/stats endpoint
- [x] Add PerfDashboard component
- [x] Log to data/perf_stats.jsonl

## Phase C: Memory Consolidation UI ✅
- [x] Create DreamStatus component
- [x] Show recent consolidations
- [x] Display new memories created
- [x] Show prune statistics
- [x] Add "Trigger Dream" button

## Phase D: Image Generation UI (Conditional) ⏭
- [x] Add ImageGenPanel with status check
- [x] Show ComfyUI availability
- [x] Prompt input with generate button
- [x] History gallery (if backend available)
- [ ] Full integration (requires ComfyUI running)

## Phase E: User Feedback Loop ✅
- [x] Add /feedback endpoint
- [x] Create FeedbackButton component
- [x] Log errors to data/kitty_errors.jsonl
- [x] Weekly usage summary endpoint
- [x] Usage tracking (anonymized)

---
Status: Ready to implement
