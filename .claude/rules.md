# Kitty Repository Rules for AI Models

## CRITICAL: Never poll CI

- Use `gh pr checks <N> --watch` (one command, exits when checks finish).
- When merge is already authorized and eligible under `AGENTS.md`/accepted Builder policy, `gh pr merge <N> --auto` may replace polling; otherwise watch checks and stop before merge.
- NEVER `until`/`while`/`for` loops with `sleep` around `gh pr` commands.
  (Blocked by .claude/hooks/block-polling.sh.)

## CRITICAL: Before ANY Push

1. **Run the narrowest relevant checks that cover your change before pushing**
   (matches `AGENTS.md` / `TESTING.md`). Full suite, lint, typecheck, and build
   are `/qg` or CI gates — do not run them on every push unless asked.
   - Backend: `python3.12 -m pytest tests/<changed_file>.py -q --tb=short`
     (fast hermetic tier; `make test` runs the whole fast tier if you really
     touched many files). Add the required process/git integration tier only
     when your change crosses a subprocess/worktree boundary: `make test-integration`.
   - Frontend: `cd gateway/kitty-chat && npm test` (Vitest unit/component); add
     `make ui-build` only when a production build is in scope.
   - If you touch routing/llm code: `python3.12 -m pytest tests/test_chat_completions.py tests/test_llm_client.py -q`
   - Broad local parity with the PR coverage gate is `make test-ci`; the full
     required Python tier is `make test-all`. Reserve these for `/qg` or an
     explicit request, not the routine pre-push loop.

2. **NEVER remove or rename symbols that tests depend on without updating the tests:**
   - Check `grep -r "symbol_name" tests/` before removing/renaming any exported function
   - If tests patch a symbol (e.g., `patch("gateway.routes.completions.route_model")`), that symbol MUST exist in the module
   - If you must remove a symbol, update ALL tests that reference it in the SAME commit

3. **NEVER push code that breaks existing tests:**
   - If a test fails because of your change, fix the test or fix your code — do not push broken code
   - Run the narrowest tests that cover your change before pushing; reserve the full suite for `/qg`/CI

## CRITICAL: PR Descriptions

Every PR description MUST include:
```
## Summary
- bullet points of what changed

## Test plan
- how to verify the change works
```

These headers match `.github/pull_request_template.md`. They are useful review
context, not an enforced CI gate — there is no `check-description` job. Do not
use `## What changed` or any other variant that diverges from the template.

## CRITICAL: Symbol Compatibility

When refactoring:
- Keep old symbols as thin wrappers for one release cycle if tests or callers depend on them
- Example: if you move `route_model` to a new module, leave `def route_model(...): return new_module.route_model(...)` in the old module
- This prevents "AttributeError: module X has no attribute Y" failures in tests

## CRITICAL: Test Mocking

When adding new hooks to components:
- Add the hook to the `vi.mock` factory in the test file
- Add the hook to the import statement at the top of the test file
- Add a default return value in `setDefaultMocks()`
- All three must be present or you get "ReferenceError: X is not defined"

## CRITICAL: Fragile Tests

- Do not assert exact markdown headers in tests (e.g., `"## What's shipped"` → use `"What's shipped" in doc`)
- Do not assert exact error messages that might change
- Use semantic checks instead of literal string matching

## CRITICAL: Multi-Model Conflicts

- If another model is working on the same branch, pull before you push
- If you get merge conflicts, resolve them and run tests again
- Do not force-push to shared branches

## Violation Consequences

If you violate these rules:
1. Your PR will fail CI checks
2. You will waste time debugging CI failures instead of building features
3. You will break other people's work

Follow these rules. They exist because they prevent the exact failures that happened on 2026-07-28.
