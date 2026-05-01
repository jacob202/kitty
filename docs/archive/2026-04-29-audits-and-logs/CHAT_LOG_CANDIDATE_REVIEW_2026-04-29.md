# Chat Log Candidate Review

Date: 2026-04-29

Source reviewed:

- `docs/imports/gemini_intake_20260428.md`
- `data/sessions/20260427_163926.json`
- `data/sessions/20260427_104140.json`
- `data/sessions/20260427_103839.json`

## Verdict

The Gemini intake is useful as a candidate list, but it is not canonical by itself. Several items are based on assistant-generated text rather than explicit user decisions. Those items must not become durable truth without user confirmation.

## Promoted To Canon

### Direct, practical, no-fluff interaction preference

Disposition: accepted

Reason:
This matches repeated current user corrections and broader project guidance, not just the Gemini draft.

Canonical location:

- `docs/USER_PREFS.md`

### Preserve raw logs until reviewed extraction exists

Disposition: accepted

Reason:
This is already a project safety rule and matches the master plan.

Canonical location:

- `docs/USER_PREFS.md`
- `docs/DECISIONS.md`

### `mlx_lm` package availability

Disposition: corrected

Reason:
The draft said MLX local inference was failing because `mlx-lm` was missing. Current validation shows `mlx_lm` imports successfully with `/opt/homebrew/bin/python3.12`.

Canonical location:

- `docs/PROJECT_FACTS.md`

Validation:

```bash
/opt/homebrew/bin/python3.12 - <<'PY'
import mlx_lm
print("mlx_lm import ok")
PY
```

## Left As Open Loops

### Canadian-first assistant persona

Disposition: needs user confirmation

Reason:
The source evidence is assistant output in the 2026-04-27 sessions. It is not strong enough to become a permanent assistant persona decision.

Open question:

Should Kitty permanently prioritize Canadian sourcing and budget-conscious recommendations, or was that a temporary/test interaction style?

### `$129/month` target price

Disposition: needs user confirmation

Reason:
The source is assistant-generated sales-style text. It is not a verified user business decision.

Open question:

Is `$129/month` a real Kitty product target, a throwaway generated claim, or irrelevant?

### Bank transaction / budget leak analysis

Disposition: privacy-gated open loop

Reason:
The idea may be useful, but it touches sensitive financial data. It needs explicit user approval and a privacy spec before parking as a buildable feature.

Open question:

Should Kitty support manual transaction paste/export analysis, and what privacy boundaries are required?

## Parked But Not Authorized

### Budget Leak Finder skill

Disposition: parked candidate

Reason:
This could become a skill later, but only after a privacy spec and skills-system validation.

### Audio specialist KB candidate from AU-7900 session text

Disposition: parked candidate

Reason:
The logs contain Sansui/AU-7900 troubleshooting text, but specialist knowledge must be source-grounded before it becomes canonical KB.

## Rejected As Noisy Extraction

### Canadian Real Estate Analysis Engine

Disposition: rejected/noisy

Reason:
The source appears to be assistant-generated prompt content, not a durable user request or project direction.

### Dead SocketIO session `sYzrlwrRFthqlGpRAAAI`

Disposition: rejected/noisy

Reason:
The source appears to be transient assistant troubleshooting text tied to an old session ID. No current code action is authorized from this extraction.

### Generic "theory-first coaching" rejection

Disposition: rejected/noisy

Reason:
This is a tone inference, not a durable product decision. The accepted canon remains: direct, practical answers, with tone adjusted to the user's live request.

## Follow-Up Rules

- Do not promote assistant-generated claims as facts without user confirmation.
- Treat `accepted_candidate` and `parked_candidate` as review labels, not final status.
- Raw logs remain preserved.
- Future chat-log extraction must separate user-authored evidence from assistant-authored inference.
