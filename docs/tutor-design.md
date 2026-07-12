# Kitty Tutor — Design & Spec (v1)

> Built for Jacob: low friction, vocabulary-first, never guesses. Reuses the
> existing Kitty RAG stack instead of adding new dependencies.

## 1. What it is
Kitty Tutor is a RAG learning scaffold. You feed it your own docs (PDF / Markdown
/ text) and it teaches concepts back to you one at a time: the key terms first, a
short plain-language explanation with a mechanical analogy, then one check-in
question. It tracks what you struggle with and reviews it later — automatically.

## 2. Why it's simple (design goals)
- **One command to teach it, one to ask.** No flags, no config, no choices.
- **It refuses to bluff.** With no docs on a topic it says so and tells you the
  exact command to fix it. No hallucination.
- **It remembers for you.** Confidence ratings drive spaced repetition, so weak
  spots come back without you tracking anything.
- **It reuses Kitty's brain.** Retrieval is `gateway.knowledge` (already backed by
  ChromaDB + `nomic-embed-text` via Ollama). No ChromaDB/FAISS addition.

## 3. Commands (the whole interface)
```
kitty tutor learn <path>          ingest a document
kitty tutor ask  "<question>"     vocab-first answer + one check-in question
kitty tutor review                list terms due for review
kitty tutor rate  "<term>" <1-3>  log confidence (1 got it, 2 need example, 3 lost)
```
HTTP equivalents for the dashboard tile:
- `POST /tutor/learn`  `{path, label?}`
- `POST /tutor/ask`    `{topic}`
- `GET  /tutor/review`

## 4. Architecture
```
kitty tutor ask "X"
      │
      ▼
gateway/tutor.py :: ask()
      │  1. retrieve(X)  → knowledge.search(collection="tutor", limit=3)
      │  2. if no chunks → TutorError("[TUTOR ALERT] I don't have docs on X…")
      │  3. build prompt (vocab-first + 3-sentence + socratic rules)
      │  4. call_llm()  → strict JSON {vocab[3], explain, question}
      │  5. parse / fail loud on malformed output
      ▼
{"vocab": [...], "explain": "...", "question": "..."}
```
State persists in `data/kitty/tutor_memory.db` (SQLite, gitignored):
- `vocabulary_terms(term, subject, last_score, next_review)`
- `user_confidence_logs(term, score, ts)`

Spaced repetition: score **1** → review in 3 days, **2** → 1 day, **3** → next
session. `due_review()` returns everything whose `next_review` has passed.

## 5. Answers follow hard rules (enforced in the prompt, checked in code)
1. Vocabulary first — 3 terms, one-line definitions.
2. Explain in ≤ 3 sentences with a simple mechanical/construction analogy.
3. End with exactly one Socratic check-in question.
4. Grounded only in retrieved docs; `{"none": true}` when the answer isn't there.

## 6. Out of scope (v1)
- Multi-doc synthesis / cross-collection debate.
- A separate Tutor model — it uses the default gateway model via `call_llm`.
- Direct shell execution of any kind (see Council design §12).

## 7. Tests
`tests/test_tutor.py` covers: zero-doc refusal, vocab/question output shape, and
confidence spacing (score 1 not due now, score 3 due immediately). Retrieval and
LLM are injected so tests run without ChromaDB/Ollama.
