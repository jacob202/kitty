# ADR 0033: Open WebUI Shell Integration Boundary

**Date:** 2026-08-05
**Status:** Accepted
**Supersedes:** Extends ADR 0027 with operational boundary details

## Context

ADR 0027 accepted Open WebUI as Kitty's replaceable daily-driver shell. The
onboarding implementation (PR #384, 2026-08-02) surfaced operational concerns
that required explicit boundary decisions:

- Open WebUI's account system conflicted with token passthrough (auth was
  disabled but the database still created pending users).
- Python `PYTHONPATH` contamination from the Kitty repository shadowed
  Open WebUI's own MCP SDK import.
- The streaming smoke test could not distinguish content arrival from parser
  disagreement.
- Open WebUI's persistent configuration overrides conflicted with Kitty's
  checked-in runtime configuration.

These are architectural concerns: the boundary between Kitty's environment and
Open WebUI's isolated environment must be explicit and enforced in code, not
operator discipline.

## Decision

The Open WebUI shell boundary is hardened with these specific rules:

1. **Environment isolation is enforced in code.** The Open WebUI process
   environment is sanitized before launch: `PYTHONPATH`, `PYTHONHOME`, and any
   other verified contaminant are removed. Child processes and LaunchAgent
   service execution inherit the sanitized environment. A regression test
   proves the isolated environment cannot resolve a repository-level module
   that shadows a third-party dependency.

2. **Auth is disabled by configuration, not database repair.** Bootstrap
   idempotently establishes the intended single-user local mode (auth disabled,
   no pending-account trap) through supported application behavior rather than
   direct SQL. If direct database repair is necessary, it is schema-aware,
   backed up, narrow in scope, and tested.

3. **Smoke tests prove real content, not just HTTP 200.**
   Acceptance verification proves first content arrival, clean terminal state,
   and surfaced error events. A parser disagreement or upstream error is
   reported with the raw event sequence for debugging, not hidden behind a
   green checkmark.

4. **Open WebUI is version-pinned.** The supported version is pinned in
   `scripts/openwebui_local.py`. Upgrades are explicit, data is backed up
   before version changes, and the Next.js Console remains a verified rollback
   target. Persistent configuration overrides in the Open WebUI database are
   disabled so checked-in runtime configuration remains authoritative.

5. **Open WebUI state is not Kitty state.** Open WebUI's internal database
   (`webui.db`) is the shell's concern. Kitty does not read from it, write to
   it, or depend on its schema. If the shell is replaced, Kitty's Gateway
   contracts remain unchanged.

## Alternatives considered

**Allow Open WebUI to inherit Kitty's environment:** Rejected. The
`PYTHONPATH` contamination bug (documented 2026-08-02) proved that
environment leakage causes hard-to-diagnose import failures. Sanitization
must be in checked-in code.

**Use Open WebUI's auth system:** Rejected. Kitty is local-first, single-user
(ADR 0002). Open WebUI's auth adds complexity with no security benefit for a
loopback-only local service.

**Have Kitty manage Open WebUI's database:** Rejected. Open WebUI's schema is
the shell's concern. Kitty's boundary is the Gateway API, not the shell's
internals.

## Evidence

- Open WebUI onboarding handoff (2026-08-02): Documented 4 defects discovered
  during real host execution.
- PYTHONPATH shadow bug: `from mcp import ClientSession` resolved to Kitty's
  `mcp/__init__.py` instead of the MCP SDK. Root cause: shell had Kitty
  project on `PYTHONPATH`.
- Pending-account trap: Despite `WEBUI_AUTH=False`, 6 duplicate
  `admin@localhost` rows with `role='pending'` were created.
- SSE smoke: "streaming smoke did not produce a complete SSE response" with
  insufficient evidence to diagnose.
- ADR 0027: Original decision to use Open WebUI as replaceable shell.

## Consequences

- **Positive:** Reliable daily-driver startup. No mysterious import failures.
  Clear separation of shell state from product state.
- **Negative:** Open WebUI upgrades may require environment sanitization
  adjustments. The `PYTHONPATH` fix is platform-specific (macOS shell
  environment).

## Risks

- Open WebUI changes its startup behavior in a future version: Mitigated by
  version pinning. Upgrades are explicit and tested.
- The isolated environment breaks a future Open WebUI feature that needs
  access to a Kitty-controlled path: Evaluate case by case. Explicit
  allowlisting is acceptable; ambient inheritance is not.

## Follow-up work

- Complete PYTHONPATH/PYTHONHOME sanitization in
  `scripts/openwebui_tool/service.py`.
- Make bootstrap idempotent for account configuration.
- Capture and inspect raw SSE event sequence; repair Gateway contract or
  verifier.
- Add regression tests for environment isolation and idempotent bootstrap.

## Related ADRs

- ADR 0027: Open WebUI as replaceable daily-driver shell
- ADR 0002: Local-first single user
- ADR 0028: Commodity software precedence
