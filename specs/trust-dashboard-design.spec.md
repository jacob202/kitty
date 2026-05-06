# Spec: Trust Dashboard & Quarantine Queue Design

Date: 2026-05-06
Status: draft

## Goal
Establish the foundational Trust & Review surfaces required for safe autonomous behavior and cognitive sharpening features. This includes a web-based Trust Dashboard (the "Control Room"), the Quarantine Queue for pending items, and Hybrid Confidence Rules for memory and action.

## Current App Boundary
Current runnable app: `/Users/jacobbrizinski/Projects/kitty`
(Per D-0014, canonical checkout after copy-first consolidation).

## Design Architecture

### 1. The Quarantine Queue ("Aware but restricted")
- **Concept:** Low-confidence memory extractions, contradictions, and high-risk autonomous actions wait here before becoming fully active.
- **System Behavior:** While an item is in quarantine, Kitty is "aware but restricted." For example, if a preference is pending, Kitty knows it exists but cannot use it as a definitive rule to govern answers or code generation. It must flag reliance on unapproved data if surfaced.
- **Data Model Requirements:** Quarantine items need to store `source_message`, `candidate_data`, `confidence_score`, `type` (memory/contradiction/action), and `status` (pending/approved/rejected).

### 2. Hybrid Confidence Model
- **Concept:** Confidence scores (0.0 - 1.0) determine if an extraction/action executes automatically or hits the queue.
- **Evaluation:** LLM self-evaluates confidence during extraction or action proposal.
- **Heuristic Caps:** Strict heuristic rules override/cap LLM confidence based on the tool or domain (e.g., `git_push` never exceeds 0.4 without terminal approval).

### 3. Trust Dashboard UI ("Control Room")
- **Scope:** A unified view of both memory quarantine and system autonomy.
- **Components:**
  - **Sidebar:** Navigation for Queue, Action Audit, Confidence Rules, API Spend.
  - **Queue List:** Displays pending items with tags (`Memory Extraction`, `Contradiction Detected`, `Action Blocked`).
  - **Item Detail:** Shows the candidate, hybrid confidence score, source evidence (quote/timestamp), and action buttons (Approve, Reject, Edit, Execute, Cancel, etc.).

## Components & Boundaries
- **Backend:** Endpoints to fetch queue items, update statuses, and adjust confidence rules. Needs to interface with `src/memory/db.py` (or a dedicated `quarantine_repo.py`).
- **Frontend (Garage UI):** React components for the Control Room layout, leveraging existing Garage UI patterns.
- **Memory Router:** Must intercept incoming extractions and route low-confidence ones to the quarantine queue rather than durable storage.

## Error Handling & Edge Cases
- **Missing Source Evidence:** If an item loses its source link, it must be flagged for manual review or dropped.
- **Duplicate Extractions:** The system should deduplicate identical extractions entering the queue.

## Testing Strategy
- **Unit Tests:** For hybrid confidence capping logic (e.g., verifying restricted tools get capped).
- **Integration Tests:** Verifying the memory router properly quarantines a candidate below threshold.
- **UI Tests:** Vitest/React Testing Library tests for rendering queue items and handling approve/reject callbacks.