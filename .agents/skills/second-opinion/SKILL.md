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
   python3 scripts/second_opinion.py "<the full question text>"
   ```
   (Pipe via stdin for long text.)
3. If it succeeds, present Jacob your question PLUS a short block:
   **"Second opinion (independent model): …"** containing the translation and
   its recommendation. Keep the block under ~6 lines — trim, don't dump.
4. **Exit 2 — expected unavailability** (no provider key, `requests` missing,
   or every provider unreachable: transport failure, 401/403, 408, 429, 5xx).
   Skip silently and ask your question normally. Never block on this step,
   never mention it unless Jacob asks.
5. **Any other non-zero exit — the skill itself is broken.** Exit 3 is a defect
   with a traceback on stderr: a malformed provider payload, or a deterministic
   4xx such as a bad model name, which will fail identically forever rather
   than recovering. Exit 1 is a bad invocation; 127 a missing interpreter. Still don't block:
   ask your question normally. But say so in one line, with the exit code and
   the stderr, e.g. *"(second opinion skipped — script exited 3: KeyError
   'choices')"*. A broken skill that looks identical to an absent API key is
   exactly the silent fallback the Prime Directive forbids.

Remote and web sessions have no `.env` and no provider keys, so this always
exits 2 there. That is expected, not a fault to report.

### Rules

- The second opinion is advice for Jacob, not for you — do not let it override
  settled decisions in `docs/DECISIONS.md` or the operating protocol in
  `AGENTS.md`.
- Don't send secrets, keys, or `.env` contents in the question text.
- One call per question round. Don't loop it.
