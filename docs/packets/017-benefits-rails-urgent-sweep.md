# Packet 017 — Benefits/admin rails + the urgent-thing sweep

- **Status:** 🧭 planned — needs an executor-ready authoring pass. The
  stakes are not hypothetical: Jacob missed the student-loan
  repayment-assistance deadline in June 2026 and it cost him ~$600 he
  didn't have. When asked what's urgent in the next 60 days he answered:
  *"there's something urgent. I don't know what it is."* This packet exists
  so that sentence can never be true silently again.
- **Best executor:** Claude Code (privacy-boundary care); deadline
  extraction prompt reviewed by strongest model.
- **Purpose:** Two jobs. (1) **Rails:** any letter, form, or PDF Jacob
  photographs or forwards becomes an ingested document with extracted
  dates, and every date becomes a watched deadline that escalates to his
  phone. (2) **The sweep:** a first-run discovery pass over everything
  reachable — Gmail signals, ingested docs, calendar — that answers "what
  is the urgent thing?" and pushes the answer to him.

## What already exists (do not rebuild)

- Capture-to-knowledge pipeline shipped in #74 (010): file/PDF/screenshot →
  inbox → ingestion. `gateway/pdf_pipeline.py`, `gateway/knowledge.py`.
- Signals + snapshots (001), triage (002), action queue (003).
- Gmail read-only connector (packet 005) supplies mail signals.
- D10: `health_admin` and `mail_body` are local-only data classes —
  extraction over letters and mail bodies runs on local models, enforced in
  `llm_client`.

## Scope sketch (for the authoring pass)

- Register `benefits-admin` as a non-code project (packet 006's table) —
  this is the OPERATOR_STRATEGY test that Kitty isn't secretly a dev tool.
- `gateway/deadline_extractor.py`: over newly ingested `health_admin` docs
  and mail signals, extract (date, obligation, amount, source) tuples →
  deadline signals with dedupe keys. Local model only. Low confidence ⇒
  `needs_jacob`, never a guess, never a drop.
- Deadline watch cron: escalating pushes via 015 at T-7d / T-3d / T-1d /
  day-of. A deadline is a row that stays open until Jacob closes it.
- **First-run sweep:** one command / one route that scans all current
  sources for date-or-amount-bearing items, ranks by proximity × stakes,
  and pushes a single report: "here's what I found that looks urgent."
  Explicitly reports what it could NOT see (no Gmail token, empty knowledge
  base) so an empty result is never mistaken for safety.
- Disability track: SAID / CDB / DTC application state lives as the
  project's next-actions (feeds packet 016's B). Kitty drafts forms and
  letters as T1 artifacts only.
- Jacob's input path stays dumb-simple: photograph the pile / share to the
  Siri shortcut / forward the email. Nothing to file, nothing to tag.

## Dependencies

- 005 (mail signals) for the sweep's highest-value source; 010 shipped;
  015 for alerts; 016 recommended so the project surfaces a B.

## Acceptance sketch

- A fixture PDF with a buried deadline produces a deadline signal and a
  scheduled escalation, end to end, with a local model stub.
- The sweep over fixtures ranks a near-dated, high-amount item first and
  names its blind spots in the same report.
- No `health_admin` content ever reaches a cloud model
  (`tests/test_llm_privacy_boundary.py` pattern extended).

## Jacob reviews

- The first live sweep report — is anything real missing from it?
- Escalation cadence (does T-7/3/1 feel like help or like nagging).

## Too broad if

- It auto-submits anything, emails anyone, or grows a benefits-eligibility
  research engine in v1 (eligibility research is a later, separate packet —
  the rails come first).
