# Plan: Fix all Council UX findings (`POST /council`)

**Goal.** Harden Council routing/synthesis so the `answer` field is always clean and self-contained, experts are chosen correctly, and the response exposes routing + timing — closing all 6 findings from the live `/council` UX review.

**Background.** Live test of `POST /council` showed: (1) compound requests whose 2nd task says "explain how it works" lose their referent and produce a clarification non-answer that gets baked into the final `answer`; (2) `ok` only means "non-empty", so a clarification question passes as success; (3) "write a python script" routes to claude via the coding+writing tie→writing rule, though config says code→deepseek; (4–6) response hides which experts ran, has no timing, and even "hi" fires a full LLM call.

**Files**
- `gateway/council.py` `[MOD]` — classify, decompose/antecedent binding, ok semantics, routing+timing metadata, greeting short-circuit.
- `gateway/routes/council.py` `[MOD]` — surface `routing` + `timings` in `CouncilResponse`.
- `tests/test_council.py` `[MOD]` — cover new behavior with the existing fake-backend pattern.
- `tests/test_council_route.py` `[MOD]` — assert new response fields.

---

**Steps**

- [ ] **High 1 — bind antecedents on decompose.** Keep `decompose()` (council.py:104) as the splitter, but in `council_route` (loop at council.py:178) rewrite any non-first segment that is referent-only. If a segment matches `\b(it|this|that|these|those|how it works|the above|the previous)\b` and lacks a concrete noun, set `instructions = f"{task} — this refers to the previous task: \"{prev_task}\""` and also inject `context["prior_task"] = prev_task` (mirror the context injection at council.py:185). This keeps `TaskDispatch` self-contained per its docstring (council.py:34), so the agent never has to guess "it".

- [ ] **High 2 — semantic `ok` + exclude non-ok from synthesis.** Replace `ok=bool(out)` at council.py:192 with `ok=_is_answer_ok(out)`. Add `_is_answer_ok(text)` returning `False` when empty, or when it matches non-answer patterns (`could you clarify`, `please specify`, `can you clarify`, `i'm unable to`, `i cannot help`, `i can't help`, `what would you like`, or a bare `<40`-char string ending in `?`). In `synthesize` (council.py:137) keep the existing "if a specialist failed, state clearly" instruction, but when building `blocks` skip the raw `p.output` for non-ok tasks and emit a `[FAILED]` note instead, so a bad subtask can't poison the merged `answer`. Single non-ok task still falls through to the combine path (the `len(parts)==1 and parts[0].ok` shortcut at council.py:139 already gates on `ok`).

- [ ] **Medium — code-gen routes to deepseek.** In `classify` (council.py:86), before the score/tie logic, add an explicit code-gen guard: if `\b(write|implement|create|build|make)\b.{0,20}\b(script|program|function|code|api|class|module|app|bot)\b` matches → return `("coding", AGENT_DEEPSEEK, "high")`. This overrides the writing tie so "write a python script" → deepseek, while "explain the code" still resolves to claude via the existing tie rule (council.py:97).

- [ ] **Low 1 — routing metadata.** Extend `CouncilOutput` (council.py:52) with `routing: list[dict]`. In `council_route` append `{"task_id", "category", "agent", "priority"}` per task (values already computed at council.py:179). Add `routing: list[dict]` to `CouncilResponse` in `gateway/routes/council.py` and return it.

- [ ] **Low 2 — timing telemetry.** In `council_route`, wrap each `backend.run` (council.py:188) with `time.perf_counter()` start/end; collect `timings: list[dict]` (`task_id`, `ms`) plus `total_ms`. Add `timings` to `CouncilOutput` and to `CouncilResponse`. (Token usage: `call_llm` doesn't expose usage — skip, noted as future.)

- [ ] **Low 3 — greeting short-circuit.** At the top of `council_route`, if `_is_greeting(user_input)` (narrow `re.fullmatch(r"(hi|hello|hey|yo|sup|thanks|thank you|ok|cool|nice)\b[!.]?", user_input.strip().lower())`) → return `CouncilOutput(answer="Hello! Tell me what to build, research, or run.", results=[], routing=[], timings=[])` with no backend call. Narrow on purpose so real prompts are never masked (prime directive: fail loud, never mask).

- [ ] **Tests.** Update `tests/test_council.py` + `tests/test_council_route.py` (mirror the existing fake-backend tests there) for: antecedent rewrite (fake `run` receives the bound instruction), semantic `ok` (fake returns a clarification string → `ok=False`, answer excludes it), code-gen routing ("write a python function to reverse a string" → `assigned_to == "deepseek"`), `routing` + `timings` present in output, and greeting short-circuit (assert `backend.run` is never called + `results == []`).

---

**Edge Cases**
- Referent segment that already names its object ("explain the csv script") → no rewrite, agent gets full context.
- All subtasks non-ok → `answer` states what couldn't be done (combine path), no empty answer.
- Single-task greeting vs "hi, write a script" → only the exact-greeting fullmatch short-circuits; the latter still routes.
- `decompose` returns one segment → loop never triggers antecedent binding.

**Risks**
- Antecedent rewrite could over-explain; mitigated by only acting on referent-only segments (pronoun present, no concrete noun).
- Greeting regex too broad could swallow real prompts; mitigated by `fullmatch` + short length + greeting-only vocabulary.

**Verification**
- Per step: `python3.12 -m pytest tests/test_council.py tests/test_council_route.py -q` must pass.
- Final live: restart gateway (`python3.12 -m uvicorn gateway.app:app --host 127.0.0.1 --port 8000`), then `curl` the 3 review prompts with `Authorization: Bearer $GATEWAY_SECRET`:
  - "write a python script to parse csv then explain how it works" → `answer` contains no "clarify" / "project kitty".
  - "write a python function to reverse a string" → `results[0].assigned_to == "deepseek"`.
  - "hi" → `results == []`, no model call, instant answer.
  - Response JSON includes `routing` and `timings` for a multi-task prompt.

**Acceptance**
- `answer` never contains a clarification question or "project kitty" for compound refs.
- non-ok subtasks are excluded (not blended) from `answer`.
- code-gen prompts route to `deepseek`.
- response exposes `routing` + `timings`.
- greetings return without an LLM call.
