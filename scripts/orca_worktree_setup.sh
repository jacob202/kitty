#!/usr/bin/env bash
set -euo pipefail

# Orca runs this as a worktree setup hook. Keep it read-only: it should orient
# the agent and fail loudly on missing repo context, not mutate the checkout.

if ! command -v git >/dev/null 2>&1; then
  echo "ERROR: git is required for KittyBuilder worktree setup." >&2
  exit 1
fi

repo_root="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [[ -z "${repo_root}" ]]; then
  echo "ERROR: not inside a git checkout; cannot load KittyBuilder setup." >&2
  exit 1
fi

cd "${repo_root}"

branch="$(git symbolic-ref --quiet --short HEAD 2>/dev/null || git rev-parse --short HEAD)"
head_sha="$(git rev-parse --short HEAD)"
dirty_count="$(git status --porcelain | wc -l | tr -d ' ')"

cat <<EOF
KittyBuilder worktree setup
===========================

Repo: ${repo_root}
Branch: ${branch}
HEAD: ${head_sha}
Dirty files: ${dirty_count}

Operating rules:
- OpenCode is the default builder/reviewer lane.
- Codex is reserved for high-risk safety review or blocked escalation.
- Local SQLite KittyBuilder queue is the future source of truth.
- GitHub issue #127 is only the temporary bridge inbox.
- No worker self-merges, broadens scope, deletes files, touches secrets, or pushes without an explicit gate.
- Failed mutations must fail loudly; no silent fallbacks or hidden retries.
- Cap silent OpenCode/provider retries quickly: one cheap attempt, one stronger attempt, then block/escalate.

Approval tiers:
- T0 auto: read-only audits, task cards, formatting, local tests, PR descriptions.
- T1 model-gated: normal scoped implementation, local commits, draft PR prep.
- T2 Jacob-gated: push, merge, destructive operations, auth/secrets/env, paid/heavy dependencies, broad scope changes.

Useful commands:
- orca worktree ps --limit 20 --json
- orca orchestration task-list --json
- opencode run -m openrouter/deepseek/deepseek-v4-flash "..."
- python3.12 -m pytest tests/test_builder_queue.py tests/test_builder_cli.py tests/test_builder_contract.py -q --tb=short

Read next:
- AGENTS.md
- docs/KITTYBUILDER_ORCA_SETUP.md
- docs/KITTYBUILDER_ORCHESTRATOR_PHASE1A.md
EOF

if [[ "${dirty_count}" != "0" ]]; then
  echo
  echo "WARNING: this worktree has uncommitted changes. Inspect before editing." >&2
fi

if [[ -n "${GITHUB_TOKEN:-}" ]]; then
  echo
  echo "WARNING: ambient GITHUB_TOKEN is set and can override gh keyring auth." >&2
  echo "Run GitHub operations with: env -u GITHUB_TOKEN gh ... (see docs/WORKFLOW.md)" >&2
fi

if ! git config --get-all credential.helper 2>/dev/null | grep -q 'gh auth git-credential'; then
  echo
  echo "WARNING: git HTTPS credentials are not routed through gh; a stale" >&2
  echo "keychain credential can fail pushes late in a build." >&2
  echo "One-time fix: gh auth setup-git" >&2
fi

missing_tools=()
for tool in orca opencode gh; do
  if ! command -v "${tool}" >/dev/null 2>&1; then
    missing_tools+=("${tool}")
  fi
done

if (( ${#missing_tools[@]} > 0 )); then
  echo
  echo "WARNING: missing optional tool(s): ${missing_tools[*]}" >&2
fi
