# Kitty code-reference documentation guidelines

These preferences apply to generated API docs under `docs/generated/` (HTML)
and to hand-written module docstrings that feed them.

## Scope

- Generated reference covers: `gateway/**/*.py` (FastAPI backend, primary —
  PEP 257 + Sphinx-style `:param:`/`:func:` field conventions), `scripts/`,
  `workers/`, `mcp/`, `integrations/` (Python), and
  `gateway/kitty-chat/src/**/*.{ts,tsx}` (TypeScript — JSDoc/TypeDoc).
- `tests/`, `gateway/tests/`, `gateway/kitty-chat/tests/` are usage-reference
  inputs only, never documented APIs.
- `docs/generated/` is build output (AST + regex extraction). Do not hand-edit
  generated HTML; fix the source docstring/comment and regenerate with the
  generator (kept outside the repo to avoid polluting the tree). History:
  first built 2026-09-17 by `/tmp/generate_code_docs.py` (since removed with
  /tmp); to regenerate, re-extract the script from this file's Format section
  or rewrite a small AST walker — the output contract is defined below.

## Format (comprehensive HTML)

- Valid HTML5, one page per module under `docs/generated/modules/`, plus
  `docs/generated/index.html` (quick reference + getting started + live filter),
  `assets/style.css`, `search_index.json`, `report.json`.
- Per module: Overview (module docstring verbatim, or `TODO: Add module
  description` placeholder when missing), Dependencies, Functions table with
  cyclomatic-complexity pills (simple 1–5 / moderate 6–10 / complex 11+),
  per-function anchors `#fn-<name>` with full signature, docstring, and a
  synthetic "Example Usage" built from the real signature (defaults shown as
  `# default:` comments; async gets `asyncio.run` wrapper), Classes with
  bases/attributes/method tables and `#cls-<name>` anchors, Constants,
  "Found in tests" (real test-file references), "See Also" sibling links.
- Navigation: every page links back via `<a href="../index.html">`; sibling
  links use `<a href="<module>.html">`; in-page anchors use `<a href="#fn-…">`.
- Keep `.goosehints` / `AGENTS.md` untouched by doc generation runs.

## Regeneration checklist

1. Regenerate per the contract in Format above; expect ~478 Python files /
   ~117 TS files / ~595 modules at 2026-09-17 HEAD `74f5d17`
   (counts drift as the tree changes — report.json is truth).
2. Validate: HTML tag balance = 0 invalid; internal `<a href>` links = 0 broken.
3. Spot-check one backend module (e.g. `gateway.db`) and one TS module for
   signature accuracy and example realism.
4. Never commit `docs/generated/` on a dirty tree — the branch already carries
   unrelated modifications; generated output belongs in its own commit/PR lane.
