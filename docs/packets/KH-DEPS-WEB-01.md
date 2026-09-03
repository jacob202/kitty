# KH-DEPS-WEB-01 — Frontend production dependencies have no known high-severity advisory

**Initiative:** none — deliberately interactive  
**Owner:** ChatGPT/Codex interactive lane after fresh collision check  
**Base authored against:** `origin/main` `70c15583a6afa4aac9a6f6eb11abf840afa377a4`  
**Depends on:** none  
**Status:** packet only — no implementation/runtime mutation performed

## Why there is no Builder manifest
This packet requires Node-only frontend verification, `.claude` compatibility-file mutation, security-sensitive live network configuration, or a combination that Builder's current packet runner cannot prove safely. Per `PACKET_STANDARD.md` F9/authority rules, it stays interactive rather than carrying fake Builder gates.

## What Jacob can do after this
Jacob can install and build the canonical Kitty frontend without the currently known high-severity production `nanoid` advisory.

## Verified finding
`npm audit --omit=dev` reported one high transitive advisory: `nanoid@3.3.16` through `@tailwindcss/postcss -> postcss`; `nanoid@6` used elsewhere is not affected. The advisory is fixable, but this is not evidence of an exploitable Kitty path.

## Intended scope
- `gateway/kitty-chat/package.json`
- `gateway/kitty-chat/package-lock.json`
- `gateway/kitty-chat/tests/packageSecurity.test.ts`


## Plan / hardened direction
1. Re-run `npm audit --omit=dev` on a fresh base and record the exact advisory graph; if it is already gone, stop.
2. Use the smallest non-forced dependency update that moves the vulnerable transitive chain to a fixed `nanoid` while preserving current Next/Tailwind majors. Do not run `npm audit fix --force`.
3. Inspect the lockfile diff for unrelated major upgrades, duplicate package explosions, install scripts, or registry/source changes.
4. Run the full frontend unit suite, typecheck, production build, and audit again.
5. If the only fix requires a major framework upgrade, do not smuggle it into this packet; report the advisory and open a separate upgrade decision.


## Acceptance criteria
1. `npm audit --omit=dev` reports zero high/critical production vulnerabilities or the exact advisory is formally accepted with evidence in a separate decision.
2. No unrelated major dependency/framework upgrade is introduced.
3. Lockfile sources remain the expected npm registry/integrity entries with no git/file URL surprise.
4. Frontend tests, TypeScript, and production build pass on the exact final lockfile.
5. The packet does not claim exploitability or security impact beyond the advisory evidence.


## Verification
- `cd gateway/kitty-chat && npm audit --omit=dev`
- `cd gateway/kitty-chat && npm test`
- `cd gateway/kitty-chat && npx tsc --noEmit`
- `cd gateway/kitty-chat && npm run build`


The implementation must demonstrate a RED reproduction or measured baseline before production edits, then exact-head GREEN evidence. User-facing changes require desktop + iPhone-class acceptance and an independent reviewer who did not implement the change.

## Stop condition
If remediation needs a major Next/Tailwind/PostCSS migration or `--force`, stop and split a framework-upgrade packet.

## Recovery / authority guard
No packet here authorizes paid provider calls, credential changes, push/PR/merge, destructive data operations, or edits to canonical while another lane owns the path. Re-read `workspace_global`, GitHub #490, current PRs/worktrees, and Builder state immediately before implementation. UNKNOWN remains UNKNOWN.
