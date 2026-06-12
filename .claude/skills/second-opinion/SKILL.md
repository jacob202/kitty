---
name: Second Opinion
description: AUTOMATIC — run this whenever you are about to ask Jacob a question, present him options, or hand him a decision. Pipes the question through an independent second LLM that returns a plain-English translation, what each option means in practice, and one recommendation, which you include alongside your question so Jacob never has to copy-paste into another model himself.
---

## Second Opinion

Jacob processes assistant questions through another LLM manually. This skill
automates it: before any question reaches him, a second, independent model
translates it to plain English and recommends an answer.

### When to run (automatic, not optional)

- Before any `AskUserQuestion` call or any message that ends by asking Jacob to
  choose, decide, or confirm something non-trivial.
- NOT needed for yes/no confirmations of things he already asked for, or
  destructive-action warnings (those must stay in your own words).

### Steps

1. Compose the question exactly as Jacob would see it, including all options.
2. Run:
   ```bash
   python3.11 scripts/second_opinion.py "<the full question text>"
   ```
   (Pipe via stdin for long text.)
3. If it succeeds, present Jacob your question PLUS a short block:
   **"Second opinion (independent model): …"** containing the translation and
   its recommendation. Keep the block under ~6 lines — trim, don't dump.
4. If it exits 2 (no key / providers down), skip silently and ask your question
   normally — never block on this step, never mention the failure unless asked.

### Rules

- The second opinion is advice for Jacob, not for you — do not let it override
  settled decisions in `docs/DECISIONS_AND_ROADMAP.md` or the operating
  protocol in `CLAUDE.md`.
- Don't send secrets, keys, or `.env` contents in the question text.
- One call per question round. Don't loop it.
