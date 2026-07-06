# ADR-0009: Lint Is High-Signal Only; E501 Not Enforced

**Status:** Accepted
**Date:** 2026-07-02

## Context

Ruff runs `select = ["E", "F", "W", "I"]` but ignores `E501`
(line-too-long). The repo runs no autoformatter, and ~87% of E501
violations are unwrappable string literals (LLM prompts, URLs,
error/log text); wrapping them hurts readability for the
lowest-signal rule in the set.

## Decision

Enforce the genuinely useful checks (undefined names, unused
imports, import order, ambiguous names). Do not enforce `E501`
until a formatter is adopted.

Why: enforcing line length without a formatter produces churn, not
safety. If `ruff format` is adopted later, re-enable `E501` — the
formatter will handle code lines and string literals can take
targeted `# noqa`.

## Consequences

- New code can exceed the line limit when a string literal demands
  it.
- A future formatter adoption flips the rule on without a code
  review, but a follow-up pass will be needed to add `# noqa` to
  the string literals.
